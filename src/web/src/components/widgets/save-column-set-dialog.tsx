import { useState, useEffect } from "react";
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
import type { ColumnDef, ColumnSet } from "@/types/models";
import { LayoutPanelLeft, List } from "lucide-react";

interface SaveColumnSetDialogProps {
  open: boolean;
  onClose: () => void;
  initialName: string;
  columns: ColumnDef[];
  existingSets: ColumnSet[];
  onSave: (name: string, isOverwrite: boolean) => void;
  isSaving?: boolean;
}

export function SaveColumnSetDialog({
  open,
  onClose,
  initialName,
  columns,
  existingSets,
  onSave,
  isSaving,
}: SaveColumnSetDialogProps) {
  const [name, setName] = useState(initialName);
  const [showSuggestions, setShowSuggestions] = useState(false);

  useEffect(() => {
    if (open) {
      setName(initialName);
      setShowSuggestions(false);
    }
  }, [open, initialName]);

  const suggestions = existingSets
    .map((s) => s.name)
    .filter((n) => n.toLowerCase().includes(name.toLowerCase()) && n !== name);

  const isOverwrite = existingSets.some(
    (s) => s.name.toLowerCase() === name.toLowerCase(),
  );

  const handleSave = () => {
    if (name.trim()) {
      onSave(name, isOverwrite);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md p-0 overflow-hidden gap-0">
        <DialogHeader className="px-6 py-4 border-b">
          <DialogTitle className="text-base flex items-center gap-2">
            <LayoutPanelLeft className="w-4 h-4 text-primary" />
            Save Column Set
          </DialogTitle>
        </DialogHeader>

        <div className="p-6 space-y-6">
          <div className="space-y-2 relative">
            <div className="flex items-center justify-between">
              <Label
                htmlFor="name"
                className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Column Set Name
              </Label>
              {isOverwrite ? (
                <span className="text-[10px] font-bold text-amber-500 uppercase px-1.5 py-0.5 bg-amber-500/10 rounded">
                  Overwrite
                </span>
              ) : (
                <span className="text-[10px] font-bold text-green-500 uppercase px-1.5 py-0.5 bg-green-500/10 rounded">
                  Create New
                </span>
              )}
            </div>
            <Input
              id="name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              placeholder="e.g. My Custom View"
              className="h-9"
              autoFocus
              autoComplete="off"
            />

            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute z-50 left-0 right-0 top-[calc(100%+4px)] bg-popover border rounded-md shadow-lg overflow-hidden max-h-[160px] overflow-y-auto">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    className="w-full text-left px-3 py-2 text-xs hover:bg-muted transition-colors border-b last:border-0 border-border"
                    onClick={() => {
                      setName(s);
                      setShowSuggestions(false);
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-3">
            <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <List className="w-3.5 h-3.5" />
              Columns Preview ({columns.length})
            </Label>
            <div className="max-h-[200px] overflow-y-auto border rounded-md bg-muted/20">
              <div className="divide-y divide-border">
                {columns.map((col) => (
                  <div
                    key={col.id}
                    className="px-3 py-2 flex items-center gap-3"
                  >
                    <div
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{
                        backgroundColor:
                          col.display_color || "var(--muted-foreground)",
                      }}
                    />
                    <span className="text-xs font-medium truncate flex-1">
                      {col.name}
                    </span>
                    <span className="text-[10px] text-muted-foreground uppercase bg-muted px-1.5 py-0.5 rounded font-bold">
                      {col.type === "value" ? "Val" : "Cnd"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
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
            onClick={handleSave}
            disabled={!name.trim() || isSaving}
            className="h-8 text-xs px-4"
          >
            {isSaving ? "Saving..." : "Save Column Set"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
