import { useState, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useListsQuery } from "@/queries/use-lists";
import { Search, List as ListIcon, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { List } from "@/types/models";

interface ListSelectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function ListSelectionDialog({
  open,
  onOpenChange,
  selectedId,
  onSelect,
}: ListSelectionDialogProps) {
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("simple");
  const { data: lists = [] } = useListsQuery();

  const categories = useMemo(() => {
    return {
      simple: lists.filter((l) => l.type === "simple"),
      combo: lists.filter((l) => l.type === "combo"),
      index: lists.filter(
        (l) => l.type === "system" && l.id.startsWith("sys:idx:"),
      ),
      market: lists.filter(
        (l) =>
          l.type === "system" &&
          (l.id.startsWith("sys:mkt:") || l.id.startsWith("sys:exc:")),
      ),
      color: lists.filter((l) => l.type === "color"),
    };
  }, [lists]);

  const handleSelect = (id: string) => {
    onSelect(id);
    onOpenChange(false);
  };

  const renderTable = (data: List[], isColorTab: boolean) => (
    <Table className="border-separate border-spacing-0">
      <TableHeader className="sticky top-0 bg-background z-20 shadow-[0_1px_0_0_rgba(0,0,0,0.1)] dark:shadow-[0_1px_0_0_rgba(255,255,255,0.1)]">
        <TableRow className="hover:bg-transparent border-b-0">
          <TableHead className="w-[30px] px-2 h-8 text-[11px] font-bold uppercase text-muted-foreground"></TableHead>
          {isColorTab && (
            <TableHead className="w-[30px] px-0 h-8 text-[11px] font-bold uppercase text-muted-foreground text-center">
              Col
            </TableHead>
          )}
          <TableHead className="h-8 text-[11px] font-bold uppercase text-muted-foreground">
            Name
          </TableHead>
          <TableHead className="text-right w-[80px] h-8 text-[11px] font-bold uppercase text-muted-foreground pr-4">
            Symbols
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.length === 0 ? (
          <TableRow>
            <TableCell
              colSpan={isColorTab ? 4 : 3}
              className="h-32 text-center text-muted-foreground text-xs"
            >
              No lists found
            </TableCell>
          </TableRow>
        ) : (
          data.map((list) => (
            <TableRow
              key={list.id}
              className={cn(
                "cursor-pointer transition-colors group h-9",
                selectedId === list.id ? "bg-primary/5" : "hover:bg-muted/50",
              )}
              onClick={() => handleSelect(list.id)}
            >
              <TableCell className="px-2">
                {selectedId === list.id && (
                  <Check className="w-3.5 h-3.5 text-primary" />
                )}
              </TableCell>
              {isColorTab && (
                <TableCell className="px-0">
                  <div
                    className="w-2.5 h-2.5 rounded-full border border-border/50 mx-auto"
                    style={{ backgroundColor: list.color || "transparent" }}
                  />
                </TableCell>
              )}
              <TableCell className="text-xs font-medium">{list.name}</TableCell>
              <TableCell className="text-right tabular-nums text-muted-foreground text-[11px] pr-4">
                {list.symbols.length}
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] p-0 overflow-hidden gap-0 flex flex-col h-[600px]">
        <DialogHeader className="px-6 py-4 border-b shrink-0">
          <DialogTitle className="text-base flex items-center gap-2">
            <ListIcon className="w-4 h-4 text-primary" />
            Select List
          </DialogTitle>
        </DialogHeader>

        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="flex flex-col flex-1 overflow-hidden"
        >
          <div className="px-6 py-2 border-b bg-muted/20 shrink-0">
            <TabsList className="w-full justify-start h-9 bg-transparent p-0 gap-1">
              <TabsTrigger
                value="simple"
                className="data-[state=active]:bg-muted px-4 text-[11px]"
              >
                Simple
              </TabsTrigger>
              <TabsTrigger
                value="combo"
                className="data-[state=active]:bg-muted px-4 text-[11px]"
              >
                Combo
              </TabsTrigger>
              <TabsTrigger
                value="index"
                className="data-[state=active]:bg-muted px-4 text-[11px]"
              >
                Index
              </TabsTrigger>
              <TabsTrigger
                value="market"
                className="data-[state=active]:bg-muted px-4 text-[11px]"
              >
                Market
              </TabsTrigger>
              <TabsTrigger
                value="color"
                className="data-[state=active]:bg-muted px-4 text-[11px]"
              >
                Color
              </TabsTrigger>
            </TabsList>
          </div>

          <div className="px-6 py-3 border-b bg-muted/20 shrink-0">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder={`Search ${activeTab} lists...`}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 h-9 bg-background text-xs"
              />
            </div>
          </div>

          <div className="flex-1 min-h-0">
            {Object.entries(categories).map(([key, data]) => {
              const tabData = search.trim()
                ? data.filter((l) =>
                    l.name.toLowerCase().includes(search.toLowerCase()),
                  )
                : data;

              return (
                <TabsContent
                  key={key}
                  value={key}
                  className="h-full m-0 border-0 p-0 outline-none data-[state=active]:flex flex-col"
                >
                  <ScrollArea className="flex-1 h-full">
                    {renderTable(tabData, key === "color")}
                  </ScrollArea>
                </TabsContent>
              );
            })}
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
