import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useUIStore } from "@/stores/ui-store";
import { useDebounce } from "@/hooks/use-debounce";
import { symbolsApi } from "@/lib/api";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import { useQuery } from "@tanstack/react-query";

export function CommandPalette() {
  const open = useUIStore((s) => s.commandPaletteOpen);
  const setOpen = useUIStore((s) => s.setCommandPaletteOpen);
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);

  const { data: results } = useQuery({
    queryKey: ["symbol-search", debouncedQuery],
    queryFn: async () => {
      if (!debouncedQuery || debouncedQuery.length < 1) return [];
      const { data } = await symbolsApi.search({
        q: debouncedQuery,
        limit: 15,
      });
      return data.data ?? data;
    },
    enabled: debouncedQuery.length >= 1,
  });

  const handleSelect = useCallback(
    (ticker: string) => {
      setOpen(false);
      setQuery("");
      navigate(`/symbols/${encodeURIComponent(ticker)}`);
    },
    [navigate, setOpen],
  );

  return (
    <CommandDialog
      open={open}
      onOpenChange={(val) => {
        setOpen(val);
        if (!val) setQuery("");
      }}
    >
      <CommandInput
        placeholder="Search symbols by ticker, name, or ISIN..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>
          {debouncedQuery.length < 1
            ? "Type to search symbols..."
            : "No symbols found."}
        </CommandEmpty>
        {results && results.length > 0 && (
          <CommandGroup heading="Symbols">
            {(
              results as Array<{
                ticker: string;
                name: string;
                type?: string;
                market?: string;
              }>
            ).map((symbol) => (
              <CommandItem
                key={symbol.ticker}
                value={symbol.ticker}
                onSelect={() => handleSelect(symbol.ticker)}
                className="flex items-center gap-3 py-2"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-medium">
                      {symbol.ticker}
                    </span>
                    {symbol.type && (
                      <Badge
                        variant="secondary"
                        className="text-[10px] h-4 px-1"
                      >
                        {symbol.type}
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground truncate">
                    {symbol.name}
                  </p>
                </div>
                {symbol.market && (
                  <span className="text-[10px] text-muted-foreground/60 uppercase">
                    {symbol.market}
                  </span>
                )}
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
