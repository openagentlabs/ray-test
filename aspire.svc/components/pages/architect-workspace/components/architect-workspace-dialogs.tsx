"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

import { architectInputClassName } from "../architect-panel-styles";

export interface ArchitectFilterDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly programValue: string;
  readonly statusValue: string;
  readonly onProgramChange: (value: string) => void;
  readonly onStatusChange: (value: string) => void;
  readonly onClear: () => void;
  readonly onApply: () => void;
}

export interface ArchitectProgramLookupDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly programOptions: readonly string[];
  readonly onSelectProgram: (program: string) => void;
}

export interface ArchitectAddTabDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
}

export interface ArchitectWorkspaceDialogsProps {
  readonly filterDialog: ArchitectFilterDialogProps;
  readonly lookupDialog: ArchitectProgramLookupDialogProps;
  readonly addTabDialog: ArchitectAddTabDialogProps;
}

export function ArchitectWorkspaceDialogs({
  filterDialog,
  lookupDialog,
  addTabDialog,
}: ArchitectWorkspaceDialogsProps) {
  return (
    <>
      <Dialog open={filterDialog.open} onOpenChange={filterDialog.onOpenChange}>
        <DialogContent className="sm:max-w-md" showCloseButton>
          <DialogHeader>
            <DialogTitle>Table filters</DialogTitle>
            <DialogDescription>
              Mock filter dialog — applies program and status constraints to the grid.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="f-prog">
                Program
              </label>
              <input
                id="f-prog"
                className={architectInputClassName}
                value={filterDialog.programValue}
                onChange={(e) => filterDialog.onProgramChange(e.target.value)}
                placeholder="Exact match (mock)"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="f-st">
                Status
              </label>
              <input
                id="f-st"
                className={architectInputClassName}
                value={filterDialog.statusValue}
                onChange={(e) => filterDialog.onStatusChange(e.target.value)}
                placeholder="e.g. Active"
              />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:justify-end">
            <Button type="button" variant="outline" onClick={filterDialog.onClear}>
              Clear
            </Button>
            <Button type="button" onClick={filterDialog.onApply}>
              Apply
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={lookupDialog.open} onOpenChange={lookupDialog.onOpenChange}>
        <DialogContent className="sm:max-w-md" showCloseButton>
          <DialogHeader>
            <DialogTitle>Lookup: program</DialogTitle>
            <DialogDescription>
              Select a value from the mock directory (lookup dialog pattern).
            </DialogDescription>
          </DialogHeader>
          <ul className="max-h-48 space-y-1 overflow-auto pr-1 text-sm">
            {lookupDialog.programOptions.map((opt) => (
              <li key={opt}>
                <button
                  type="button"
                  className="flex w-full rounded-md px-2 py-1.5 text-left hover:bg-accent hover:text-accent-foreground"
                  onClick={() => lookupDialog.onSelectProgram(opt)}
                >
                  {opt}
                </button>
              </li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>

      <Dialog open={addTabDialog.open} onOpenChange={addTabDialog.onOpenChange}>
        <DialogContent className="sm:max-w-sm" showCloseButton>
          <DialogHeader>
            <DialogTitle>Add tab</DialogTitle>
            <DialogDescription>
              Placeholder for tab configuration. No persistence in this mock.
            </DialogDescription>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            In a full implementation this dialog would add or remove workspace tabs.
          </p>
          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              onClick={() => addTabDialog.onOpenChange(false)}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
