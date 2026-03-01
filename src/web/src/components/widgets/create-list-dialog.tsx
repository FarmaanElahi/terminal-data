import { useState, useEffect, useMemo } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useListsQuery, useCreateListMutation } from "@/queries/use-lists";
import type { List, ListType } from "@/types/models";
import { ListPlus, Layers, Combine, Palette, X, Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface CreateListDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (list: List) => void;
}

const LIST_TYPE_OPTIONS: {
  value: ListType;
  label: string;
  description: string;
  icon: typeof ListPlus;
  disabled?: boolean;
}[] = [
  {
    value: "simple",
    label: "Simple",
    description: "Add and remove symbols manually",
    icon: Layers,
  },
  {
    value: "combo",
    label: "Combo",
    description: "Combine symbols from other lists",
    icon: Combine,
  },
  {
    value: "color",
    label: "Color",
    description: "Auto-created, rename only",
    icon: Palette,
    disabled: true,
  },
];

export function CreateListDialog({
  open,
  onClose,
  onCreated,
}: CreateListDialogProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState<ListType>("simple");
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [sourceSearch, setSourceSearch] = useState("");

  const { data: lists = [] } = useListsQuery();
  const createList = useCreateListMutation();

  // Non-color lists available for combo source selection
  const sourceLists = useMemo(
    () => lists.filter((l) => l.type !== "color"),
    [lists],
  );

  useEffect(() => {
    if (open) {
      setName("");
      setType("simple");
      setSelectedSourceIds([]);
      setSourceSearch("");
    }
  }, [open]);

  const toggleSource = (id: string) => {
    setSelectedSourceIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const canSubmit =
    name.trim().length > 0 &&
    (type !== "combo" || selectedSourceIds.length > 0);

  const handleCreate = async () => {
    if (!canSubmit) return;
    try {
      const newList = await createList.mutateAsync({
        name: name.trim(),
        type: type as "simple" | "color" | "combo",
        ...(type === "combo" ? { source_list_ids: selectedSourceIds } : {}),
      });
      onCreated?.(newList);
      onClose();
    } catch (err) {
      console.error("Failed to create list:", err);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md p-0 overflow-hidden gap-0">
        <DialogHeader className="px-6 py-4 border-b">
          <DialogTitle className="text-base flex items-center gap-2">
            <ListPlus className="w-4 h-4 text-primary" />
            Create List
          </DialogTitle>
        </DialogHeader>

        <div className="p-6 space-y-6">
          {/* Name */}
          <div className="space-y-2">
            <Label
              htmlFor="list-name"
              className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              Name
            </Label>
            <Input
              id="list-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My Watchlist"
              className="h-9"
              autoFocus
              autoComplete="off"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate();
              }}
            />
          </div>

          {/* Type selector */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Type
            </Label>
            <div className="grid grid-cols-3 gap-2">
              {LIST_TYPE_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const selected = type === opt.value;
                return (
                  <button
                    key={opt.value}
                    disabled={opt.disabled}
                    onClick={() => !opt.disabled && setType(opt.value)}
                    className={cn(
                      "relative flex flex-col items-center gap-1.5 rounded-lg border p-3 text-center transition-all",
                      selected
                        ? "border-primary bg-primary/5 text-foreground"
                        : "border-border text-muted-foreground hover:border-primary/40 hover:bg-muted/30",
                      opt.disabled &&
                        "opacity-40 cursor-not-allowed hover:border-border hover:bg-transparent",
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="text-xs font-medium">{opt.label}</span>
                    <span className="text-[10px] leading-tight opacity-70">
                      {opt.description}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Source lists for combo */}
          {type === "combo" && (
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Source Lists
              </Label>

              {/* Selected list chips */}
              {selectedSourceIds.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {selectedSourceIds.map((id) => {
                    const list = sourceLists.find((l) => l.id === id);
                    if (!list) return null;
                    return (
                      <span
                        key={id}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-medium"
                      >
                        {list.name}
                        <button
                          onClick={() => toggleSource(id)}
                          className="hover:text-destructive transition-colors"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    );
                  })}
                </div>
              )}

              {sourceLists.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No lists available. Create a simple list first.
                </p>
              ) : (
                <>
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                    <Input
                      value={sourceSearch}
                      onChange={(e) => setSourceSearch(e.target.value)}
                      placeholder="Search lists..."
                      className="h-8 pl-8 text-xs"
                      autoComplete="off"
                    />
                  </div>
                  {sourceSearch.trim() && (
                    <div className="max-h-40 overflow-y-auto border rounded-md bg-muted/20 divide-y divide-border">
                      {sourceLists
                        .filter(
                          (l) =>
                            l.name
                              .toLowerCase()
                              .includes(sourceSearch.toLowerCase()) &&
                            !selectedSourceIds.includes(l.id),
                        )
                        .map((l) => (
                          <button
                            key={l.id}
                            onClick={() => {
                              toggleSource(l.id);
                              setSourceSearch("");
                            }}
                            className="w-full flex items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-muted/30"
                          >
                            <span className="text-xs font-medium truncate">
                              {l.name}
                            </span>
                            <span className="text-[10px] text-muted-foreground uppercase ml-auto shrink-0">
                              {l.type}
                            </span>
                          </button>
                        ))}
                      {sourceLists.filter(
                        (l) =>
                          l.name
                            .toLowerCase()
                            .includes(sourceSearch.toLowerCase()) &&
                          !selectedSourceIds.includes(l.id),
                      ).length === 0 && (
                        <p className="px-3 py-2 text-xs text-muted-foreground">
                          No matching lists
                        </p>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="px-6 py-4 bg-muted/30 border-t flex sm:justify-between items-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-8 text-xs"
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleCreate}
            disabled={!canSubmit || createList.isPending}
            className="h-8 text-xs px-4"
          >
            {createList.isPending ? "Creating..." : "Create List"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
