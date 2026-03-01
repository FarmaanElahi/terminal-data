import { useQuery } from "@tanstack/react-query";
import { communityApi } from "@/lib/api";
import { QUERY_KEYS } from "./query-keys";
import type { StockTwitsFeedResponse } from "@/types/models";

export function useCommunitySymbolFeed(
  symbol: string | null,
  feed: string,
  limit?: number,
) {
  return useQuery({
    queryKey: QUERY_KEYS.communityFeed("symbol", `${symbol}:${feed}`),
    queryFn: () =>
      communityApi
        .symbolFeed(symbol!, feed, limit)
        .then((r) => r.data as StockTwitsFeedResponse),
    enabled: !!symbol && !!feed,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}

export function useCommunityGlobalFeed(feed: string, limit?: number) {
  return useQuery({
    queryKey: QUERY_KEYS.communityFeed("global", feed),
    queryFn: () =>
      communityApi
        .globalFeed(feed, limit)
        .then((r) => r.data as StockTwitsFeedResponse),
    enabled: !!feed,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}
