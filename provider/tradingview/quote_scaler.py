import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, AsyncGenerator, Tuple
from provider.tradingview.quote_streamer import TradingViewQuoteStreamer, QuoteStreamEvent

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TradingViewScaler")


@dataclass
class StreamingNode:
    id: str
    tickers: Set[str] = field(default_factory=set)
    max_tickers: int = 100


class TradingViewScaler:
    def __init__(
        self,
        quote_fields: List[str],
        max_connections: int = 4,
        max_tickers_per_connection: int = 1000,
    ):
        self.quote_fields = tuple(quote_fields)
        self.max_connections = max_connections
        self.max_tickers_per_connection = max_tickers_per_connection

        self.nodes: Dict[str, StreamingNode] = {}
        self.ticker_to_node: Dict[str, str] = {}
        self.node_tasks: Dict[str, asyncio.Task] = {}
        self.node_streamers: Dict[str, TradingViewQuoteStreamer] = {}
        self.quotes: Dict[str, Dict[str, Any]] = {}
        self._event_queues: Dict[str, asyncio.Queue] = {}
        self.running = False

    async def start(self):
        if not self.running:
            self.running = True
            logger.info("Scaler started")

    async def stop(self):
        if self.running:
            self.running = False
            for task in self.node_tasks.values():
                task.cancel()
            await asyncio.gather(*self.node_tasks.values(), return_exceptions=True)
            self.nodes.clear()
            self.node_tasks.clear()
            self.node_streamers.clear()
            self.ticker_to_node.clear()
            self._event_queues.clear()
            logger.info("Scaler stopped")

    async def add_tickers(self, tickers: List[str]):
        await self.start()
        new_tickers = [t for t in tickers if t not in self.ticker_to_node]
        if not new_tickers:
            return

        node_assignments: Dict[str, List[str]] = {}
        unassigned = new_tickers[:]

        for node_id, node in self.nodes.items():
            capacity = node.max_tickers - len(node.tickers)
            if capacity > 0:
                to_add = unassigned[:capacity]
                if to_add:
                    node_assignments.setdefault(node_id, []).extend(to_add)
                    unassigned = unassigned[capacity:]

        while unassigned and len(self.nodes) < self.max_connections:
            node_id = f"node_{len(self.nodes) + 1}"
            batch = unassigned[:self.max_tickers_per_connection]
            node_assignments[node_id] = batch
            unassigned = unassigned[self.max_tickers_per_connection:]

        for node_id, assigned in node_assignments.items():
            node = self.nodes.setdefault(node_id, StreamingNode(id=node_id, max_tickers=self.max_tickers_per_connection))
            node.tickers.update(assigned)
            for t in assigned:
                self.ticker_to_node[t] = node_id

        await self._update_nodes(set(node_assignments.keys()))

    async def remove_tickers(self, tickers: List[str]):
        affected_nodes = set()
        node_ticker_map: Dict[str, List[str]] = {}

        for t in tickers:
            node_id = self.ticker_to_node.pop(t, None)
            if node_id and node_id in self.nodes:
                self.nodes[node_id].tickers.discard(t)
                node_ticker_map.setdefault(node_id, []).append(t)
                self.quotes.pop(t, None)
                affected_nodes.add(node_id)

        for node_id, symbols in node_ticker_map.items():
            streamer = self.node_streamers.get(node_id)
            if streamer:
                await streamer.remove_symbols(symbols)

        await self._update_nodes(affected_nodes)

    async def _update_nodes(self, node_ids: Set[str]):
        for node_id in node_ids:
            node = self.nodes.get(node_id)
            if not node or not node.tickers:
                task = self.node_tasks.pop(node_id, None)
                if task and not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                self.node_streamers.pop(node_id, None)
                self._event_queues.pop(node_id, None)
                self.nodes.pop(node_id, None)
                continue

            if node_id in self.node_tasks:
                task = self.node_tasks.pop(node_id)
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

            event_queue = asyncio.Queue()
            self._event_queues[node_id] = event_queue
            task = asyncio.create_task(self._run_node(node_id, list(node.tickers), event_queue))
            self.node_tasks[node_id] = task

    async def _run_node(self, node_id: str, tickers: List[str], queue: asyncio.Queue):
        logger.info(f"Node {node_id} started with {len(tickers)} tickers")
        streamer = TradingViewQuoteStreamer(fields=self.quote_fields)
        self.node_streamers[node_id] = streamer

        try:
            async for event_type, ticker, data in streamer.stream_quotes(tickers):
                if not self.running:
                    break

                await queue.put((event_type, ticker, data))
                if event_type == QuoteStreamEvent.QUOTE_UPDATE:
                    self.quotes[ticker] = data

        except asyncio.CancelledError:
            logger.info(f"Node {node_id} cancelled.")
        except Exception as e:
            logger.error(f"Node {node_id} error: {e}")
        finally:
            logger.info(f"Node {node_id} stopped.")

    async def quote_events(self) -> AsyncGenerator[Tuple[str, Optional[str], Any], None]:
        """Yields all quote events from all nodes."""
        while self.running:
            tasks = [q.get() for q in self._event_queues.values() if not q.empty()]
            if not tasks:
                await asyncio.sleep(0.1)
                continue
            for coro in asyncio.as_completed(tasks):
                try:
                    yield await coro
                except Exception as e:
                    logger.error(f"Failed to yield quote event: {e}")

    def get_quote(self, ticker: str) -> Dict[str, Any]:
        return self.quotes.get(ticker, {})

    def get_all_quotes(self) -> Dict[str, Dict[str, Any]]:
        return self.quotes.copy()