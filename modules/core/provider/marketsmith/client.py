import asyncio
import httpx
from httpx_retries import Retry, RetryTransport
from typing import Optional, Dict, Any
from datetime import datetime, date


class MarketSmithError(Exception):
    """Base exception for MarketSmith API errors"""
    pass


class SessionNotInitializedError(MarketSmithError):
    """Raised when trying to use client before initialization"""
    pass


class SymbolNotFoundError(MarketSmithError):
    """Raised when symbol is not found in search results"""
    pass


class SymbolNotSetError(MarketSmithError):
    """Raised when trying to access symbol-specific data without setting a symbol first"""
    pass


class MarketSmithClient:
    BASE_URL = "https://marketsmithindia.com"
    USER_ID = 3990
    INIT_URL = f"{BASE_URL}/mstool/eval/0innse50/evaluation.jsp#/"
    SEARCH_URL = f"{BASE_URL}/gateway/simple-api/ms-india/instr/srch.json"
    ADD_SYMBOL_URL = f"{BASE_URL}/gateway/api/ms-india/instr/addrecentsymbol.json"
    HEADER_DETAILS_URL = f"{BASE_URL}/gateway/simple-api/ms-india/instr/0/{{instrument_id}}/eHeaderDetails.json"
    SYMBOL_DETAILS_URL = f"{BASE_URL}/gateway/simple-api/ms-india/instr/0/{{instrument_id}}/symboldetails.json"
    FINANCE_DETAILS_URL = f"{BASE_URL}/gateway/simple-api/ms-india/instr/0/{{instrument_id}}/financeDetails.json"
    BROKER_ESTIMATES_URL = f"{BASE_URL}/gateway/simple-api/ms-india/getBrokerEstimates.json"
    RED_FLAGS_URL = f"{BASE_URL}/gateway/simple-api/ms-india/instr/{{instrument_id}}/getRedFlags.json"
    # Add this URL to the existing class URLs at the top
    BULK_BLOCK_DEALS_URL = f"{BASE_URL}/gateway/simple-api/ms-india/{{instrument_id}}/getBulkBlockDeals.json"
    # Add this URL to the existing class URLs at the top
    WISDOM_URL = f"{BASE_URL}/gateway/simple-api/ms-india/instr/0/{{instrument_id}}/wisdom.json"
    retry = Retry(total=5, backoff_factor=0.5)
    transport = RetryTransport(retry=retry)

    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.ms_auth: Optional[str] = None
        self.ms_session_id: Optional[str] = None
        self.current_symbol: Optional[str] = None
        self.current_instrument_id: Optional[str] = None

        # Common headers for API requests
        self.common_headers = {
            "Accept": "*/*",
            "Accept-Language": "en-IN,en;q=0.9,ar-EG;q=0.8,ar;q=0.7,en-US;q=0.6,ar-XB;q=0.5,en-GB;q=0.4",
            "Cache-Control": "no-cache",
            "DNT": "1",
            "Pragma": "no-cache",
            "Priority": "u=1, i",
            "Sec-CH-UA": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest"
        }

    def _convert_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert parameters by replacing spaces with + in string values"""
        converted_params = {}
        for key, value in params.items():
            if isinstance(value, str) and ' ' in value:
                converted_params[key] = '+'.join(value.split(' '))
            else:
                converted_params[key] = value
        return converted_params

    def _get_headers_with_referer(self) -> Dict[str, str]:
        """Get common headers with symbol-specific referer"""
        headers = self.common_headers.copy()
        if self.current_symbol:
            headers["Referer"] = f"{self.BASE_URL}/mstool/eval/{self.current_symbol.lower()}/evaluation.jsp"
        return headers

    async def _make_request(self, method: str, url: str, params: Optional[Dict[str, Any]] = None,
                            headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
        """Make HTTP request with error handling and logging"""
        try:
            if params:
                converted_params = self._convert_params(params)
            else:
                converted_params = {}

            if method.upper() == "GET":
                resp = await self.client.get(url, params=converted_params, headers=headers, **kwargs)
            elif method.upper() == "POST":
                resp = await self.client.post(url, params=converted_params, headers=headers, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            resp.raise_for_status()
            return resp

        except Exception as e:
            print(f"HTTP Request Failed:")
            print(f"Method: {method.upper()}")
            print(f"URL: {url}")
            print(f"Params: {params}")
            print(f"Error: {str(e)}")
            raise

    async def init_session(self):
        """Initialize the client session and handle cookie authentication"""
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/137.0.0.0 Safari/537.36"
                ),
                "Accept": "*/*",
                "DNT": "1",
                "Origin": self.BASE_URL,
                "X-Requested-With": "XMLHttpRequest",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            },
            timeout=20.0,
            follow_redirects=True
        )

        # Initialize session and let cookies populate
        resp = await self.client.get(self.INIT_URL)
        resp.raise_for_status()

        print("Session initialized")

        # Store MSSESSIONID
        self.ms_session_id = self.client.cookies.get("MSSESSIONID")
        if not self.ms_session_id:
            raise RuntimeError("MSSESSIONID cookie not found")

        # Handle msAuth: remove the first one if there are two
        auth_cookies = [
            c for c in self.client.cookies.jar if c.name == "msAuth"
        ]

        if not auth_cookies:
            raise RuntimeError("msAuth cookie not found")

        if len(auth_cookies) >= 2:
            # Remove first msAuth cookie
            self.client.cookies.jar.clear(domain=auth_cookies[0].domain, path=auth_cookies[0].path, name="msAuth")
            # Add second msAuth manually (preserve it)
            self.ms_auth = auth_cookies[1].value
            self.client.cookies.set(
                "msAuth",
                self.ms_auth,
                domain=auth_cookies[1].domain,
                path=auth_cookies[1].path,
            )
        else:
            self.ms_auth = auth_cookies[0].value

        print(f"Session initialized successfully. MS Session ID: {self.ms_session_id}")

    async def set_symbol(self, symbol: str):
        symbol = symbol.replace("_", "-")
        """Set the current symbol for all future symbol-specific API calls"""
        if not self.client:
            raise SessionNotInitializedError("Session not initialized. Call init_session() first.")

        # Search symbol
        params = {
            "text": symbol,
            "lang": "en",
            "ver": "2"
        }

        search_resp = await self._make_request("GET", self.SEARCH_URL, params=params)
        results = search_resp.json().get("response", {}).get("results", [])
        match = next(
            (r for r in results if r.get("symbol", "").upper() == symbol.upper()),
            None
        )
        if not match:
            raise SymbolNotFoundError(f"Symbol '{symbol}' not found in search results.")

        instrument_id = match["instrumentId"]

        # Attach symbol to session
        payload = {
            "instrumentId": instrument_id,
            "userId": self.USER_ID,
        }

        post_resp = await self.client.post(
            self.ADD_SYMBOL_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        post_resp.raise_for_status()

        # Store current symbol and instrument ID for future use
        self.current_symbol = symbol.upper()
        self.current_instrument_id = instrument_id

        print(f"Symbol set successfully: {self.current_symbol} (ID: {self.current_instrument_id})")

    async def basic_market(self,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           page: int = 1,
                           benchmark: str = "0IBOMSEN",
                           ie: int = 0,
                           iq: int = 0) -> Dict[str, Any]:
        """
        Get basic market data for the currently set symbol

        Args:
            start_date: Start date in YYYYMMDD format (defaults to ~5 years ago)
            end_date: End date in YYYYMMDD format (defaults to today)
            page: Page number (default: 1)
            benchmark: Benchmark index (default: "0IBOMSEN")
            ie: IE parameter (default: 0)
            iq: IQ parameter (default: 0)

        Returns:
            Dict containing the market data response

        Raises:
            SessionNotInitializedError: If session is not initialized
            SymbolNotSetError: If no symbol has been set
        """
        if not self.client:
            raise SessionNotInitializedError("Session not initialized. Call init_session() first.")

        if not self.current_symbol or not self.current_instrument_id:
            raise SymbolNotSetError("No symbol set. Call set_symbol() first.")

        # Set default dates if not provided
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            # Default to approximately 5 years ago
            start_year = datetime.now().year - 5
            start_date = f"{start_year}0101"

        # Build the URL with instrument ID
        url = self.HEADER_DETAILS_URL.format(instrument_id=self.current_instrument_id)

        # Build query parameters
        params = {
            "p": page,
            "s": start_date,
            "e": end_date,
            "b": benchmark,
            "ie": ie,
            "iq": iq,
            "ms-auth": self.ms_session_id
        }

        # Make the request
        resp = await self._make_request("GET", url, params=params, headers=self._get_headers_with_referer())
        response_data = resp.json()
        return response_data.get("headerDetails", {})

    async def details(self,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      language: str = "en",
                      is_consolidated: int = 0) -> Dict[str, Any]:
        """
        Get detailed symbol information for the currently set symbol

        Args:
            start_date: Start date in YYYYMMDD format (defaults to ~5 years ago)
            end_date: End date in YYYYMMDD format (defaults to today)
            language: Language code (default: "en")
            is_consolidated: Consolidated flag (default: 0)

        Returns:
            Dict containing the symbol details response

        Raises:
            SessionNotInitializedError: If session is not initialized
            SymbolNotSetError: If no symbol has been set
        """
        if not self.client:
            raise SessionNotInitializedError("Session not initialized. Call init_session() first.")

        if not self.current_symbol or not self.current_instrument_id:
            raise SymbolNotSetError("No symbol set. Call set_symbol() first.")

        # Set default dates if not provided
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            # Default to approximately 5 years ago
            start_year = datetime.now().year - 5
            start_date = f"{start_year}0618"

        # Build the URL with instrument ID
        url = self.SYMBOL_DETAILS_URL.format(instrument_id=self.current_instrument_id)

        # Build query parameters
        params = {
            "s": start_date,
            "e": end_date,
            "text": self.current_symbol,
            "lang": language,
            "isConsolidated": is_consolidated,
            "ms-auth": self.ms_session_id
        }

        # Make the request
        resp = await self._make_request("GET", url, params=params, headers=self._get_headers_with_referer())
        response_data = resp.json()
        return response_data.get("response", {})

    async def finance_details(self, is_consolidated: bool = False) -> Dict[str, Any]:
        """
        Get financial details for the currently set symbol

        Args:
            is_consolidated: Whether to return consolidated financial data (default: False)

        Returns:
            Dict containing the financial details response

        Raises:
            SessionNotInitializedError: If session is not initialized
            SymbolNotSetError: If no symbol has been set
        """
        if not self.client:
            raise SessionNotInitializedError("Session not initialized. Call init_session() first.")

        if not self.current_symbol or not self.current_instrument_id:
            raise SymbolNotSetError("No symbol set. Call set_symbol() first.")

        # Build the URL with instrument ID
        url = self.FINANCE_DETAILS_URL.format(instrument_id=self.current_instrument_id)

        # Build query parameters
        params = {
            "isConsolidated": str(is_consolidated).lower(),
            "ms-auth": self.ms_session_id
        }

        # Make the request
        resp = await self._make_request("GET", url, params=params, headers=self._get_headers_with_referer())
        return resp.json()

    async def broker_estimates(self) -> Dict[str, Any]:
        """
        Get broker estimates for the currently set symbol
        Raises:
            SessionNotInitializedError: If session is not initialized
            SymbolNotSetError: If no symbol has been set
        """
        if not self.client:
            raise SessionNotInitializedError("Session not initialized. Call init_session() first.")

        if not self.current_symbol or not self.current_instrument_id:
            raise SymbolNotSetError("No symbol set. Call set_symbol() first.")

        # Build query parameters
        params = {
            "instrumentId": self.current_instrument_id,
            "ms-auth": self.ms_session_id
        }

        # Make the request
        resp = await self._make_request("GET", self.BROKER_ESTIMATES_URL, params=params, headers=self._get_headers_with_referer())
        response_data = resp.json()
        return response_data.get('response', {}).get('results', {})

    async def red_flags(self) -> Dict[str, Any]:
        """
        Get red flags data for the currently set symbol

        Returns:
            Dict containing the red flags data

        Raises:
            SessionNotInitializedError: If session is not initialized
            SymbolNotSetError: If no symbol has been set
        """
        if not self.client:
            raise SessionNotInitializedError("Session not initialized. Call init_session() first.")

        if not self.current_symbol or not self.current_instrument_id:
            raise SymbolNotSetError("No symbol set. Call set_symbol() first.")

        # Build the URL with instrument ID
        url = self.RED_FLAGS_URL.format(instrument_id=self.current_instrument_id)

        # Build query parameters
        params = {
            "ms-auth": self.ms_session_id
        }

        # Make the request
        resp = await self._make_request("GET", url, params=params, headers=self._get_headers_with_referer())
        response_data = resp.json()
        return response_data.get('response', {}).get('results', {})

    async def bulk_block_deals(self) -> Dict[str, Any]:
        """
        Get bulk and block deals data for the currently set symbol

        Returns:
            Dict containing the bulk and block deals data

        Raises:
            SessionNotInitializedError: If session is not initialized
            SymbolNotSetError: If no symbol has been set
        """
        if not self.client:
            raise SessionNotInitializedError("Session not initialized. Call init_session() first.")

        if not self.current_symbol or not self.current_instrument_id:
            raise SymbolNotSetError("No symbol set. Call set_symbol() first.")

        # Build the URL with instrument ID
        url = self.BULK_BLOCK_DEALS_URL.format(instrument_id=self.current_instrument_id)

        # Build query parameters
        params = {
            "ms-auth": self.ms_session_id
        }

        # Make the request
        resp = await self._make_request("GET", url, params=params, headers=self._get_headers_with_referer())
        response_data = resp.json()
        return response_data.get('response', {}).get('results', {})

    async def wisdom(self,
                     language: str = "en",
                     version: str = "2") -> Dict[str, Any]:
        """
        Get wisdom data for the currently set symbol

        Args:
            language: Language code (default: "en")
            version: API version (default: "2")

        Returns:
            Dict containing the wisdom data

        Raises:
            SessionNotInitializedError: If session is not initialized
            SymbolNotSetError: If no symbol has been set
        """
        if not self.client:
            raise SessionNotInitializedError("Session not initialized. Call init_session() first.")

        if not self.current_symbol or not self.current_instrument_id:
            raise SymbolNotSetError("No symbol set. Call set_symbol() first.")

        # Build the URL with instrument ID
        url = self.WISDOM_URL.format(instrument_id=self.current_instrument_id)

        # Build query parameters
        params = {
            "lang": language,
            "ver": version,
            "x": "y",  # Required parameter as per the API
            "ms-auth": self.ms_session_id
        }

        # Make the request
        resp = await self._make_request("GET", url, params=params, headers=self._get_headers_with_referer())
        response_data = resp.json()
        return response_data.get('response', {}).get('results', {})

    async def all(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch all available data for the currently set symbol in parallel.
        This method will fetch all data concurrently for better performance.

        Args:
            symbol: Symbol

        Returns:
            Dict containing all fetched data

        Raises:
            SessionNotInitializedError: If session is not initialized
            SymbolNotSetError: If no symbol has been set
        """
        await self.set_symbol(symbol)

        # Create tasks for all data fetching operations
        tasks = [
            self.basic_market(),
            self.details(),
            self.finance_details(is_consolidated=True),
            self.finance_details(is_consolidated=False),
            self.broker_estimates(),
            self.red_flags(),
            self.bulk_block_deals()
        ]

        try:
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks)

            # Pack results into a dictionary
            return {
                "basic_market": results[0],
                "details": results[1],
                "consolidate_finance_details": results[2],
                "standalone_finance_details": results[3],
                "broker_estimates": results[4],
                "red_flags": results[5],
                "bulk_block_deals": results[6]
            }

        except Exception as e:
            # Wrap any errors with additional context
            raise MarketSmithError(f"Error fetching symbol data: {str(e)}") from e

    def get_current_symbol(self) -> Optional[str]:
        """Get the currently set symbol"""
        return self.current_symbol

    def get_current_instrument_id(self) -> Optional[str]:
        """Get the current instrument ID"""
        return self.current_instrument_id

    async def close(self):
        """Close the HTTP client and clean up resources"""
        if self.client:
            await self.client.aclose()
            self.client = None
            self.current_symbol = None
            self.current_instrument_id = None
            self.transport.close()