import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useState } from "react";

export function ScreenerToolbar() {
  const [filterActive, setFilterActive] = useState(false);
  const [timeframe, setTimeframe] = useState("D");

  return (
    <div className="border-b border-border px-4 py-1.5 flex items-center gap-3 bg-card/20 text-xs shrink-0">
      {/* Filter toggle */}
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Filter:</span>
        <Button
          variant={filterActive ? "default" : "outline"}
          size="sm"
          className="h-6 text-[11px] px-2"
          onClick={() => setFilterActive(!filterActive)}
        >
          {filterActive ? (
            <>
              <svg
                className="w-3 h-3 mr-1"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4.5 12.75l6 6 9-13.5"
                />
              </svg>
              Active
            </>
          ) : (
            "Inactive"
          )}
        </Button>
      </div>

      {/* Separator */}
      <div className="w-px h-4 bg-border" />

      {/* Timeframe */}
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Timeframe:</span>
        <Select value={timeframe} onValueChange={setTimeframe}>
          <SelectTrigger className="h-6 w-14 text-[11px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="D" className="text-xs">
              D
            </SelectItem>
            <SelectItem value="W" className="text-xs">
              W
            </SelectItem>
            <SelectItem value="M" className="text-xs">
              M
            </SelectItem>
            <SelectItem value="Y" className="text-xs">
              Y
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Separator */}
      <div className="w-px h-4 bg-border" />

      {/* Live indicator */}
      <Badge variant="secondary" className="text-[10px] h-5 gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
        Live
      </Badge>
    </div>
  );
}
