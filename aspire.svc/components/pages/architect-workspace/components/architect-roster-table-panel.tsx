"use client";

import type { RefObject } from "react";
import { Fragment } from "react";
import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type {
  ArchitectRosterRow,
  ArchitectRosterSortEntry,
  ArchitectRosterSortKey,
} from "../architect-types";
import { architectPanelClassName } from "../architect-panel-styles";

export interface ArchitectRosterTablePanelProps {
  readonly title: string;
  readonly description: string;
  readonly isLoading?: boolean;
  readonly rows: readonly ArchitectRosterRow[];
  readonly sorts: readonly ArchitectRosterSortEntry[];
  readonly onSort: (column: ArchitectRosterSortKey) => void;
  readonly selectedIds: ReadonlySet<string>;
  readonly onToggleRow: (id: string) => void;
  readonly allVisibleSelected: boolean;
  readonly selectAllCheckboxRef: RefObject<HTMLInputElement | null>;
  readonly onToggleSelectAllVisible: () => void;
  readonly expandedRowId: string | undefined;
  readonly onExpandedRowChange: (id: string | undefined) => void;
  readonly onOpenFilterDialog: () => void;
  readonly onInsertRow: () => void;
  readonly onDeleteSelected: () => void;
  readonly deleteSelectedDisabled: boolean;
}

const TABLE_COLUMNS: readonly {
  readonly key: ArchitectRosterSortKey;
  readonly label: string;
}[] = Object.freeze([
  { key: "caseId", label: "Case ID" },
  { key: "memberName", label: "Member" },
  { key: "program", label: "Program" },
  { key: "status", label: "Status" },
  { key: "nextReview", label: "Next review" },
]);

export function ArchitectRosterTablePanel({
  title,
  description,
  isLoading,
  rows,
  sorts,
  onSort,
  selectedIds,
  onToggleRow,
  allVisibleSelected,
  selectAllCheckboxRef,
  onToggleSelectAllVisible,
  expandedRowId,
  onExpandedRowChange,
  onOpenFilterDialog,
  onInsertRow,
  onDeleteSelected,
  deleteSelectedDisabled,
}: ArchitectRosterTablePanelProps) {
  const sortIndicator = (column: ArchitectRosterSortKey) => {
    const entry = sorts.find((s) => s.column === column);
    if (!entry) {
      return null;
    }
    const Icon = entry.direction === "asc" ? ArrowUp : ArrowDown;
    return <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />;
  };

  return (
    <div
      className={cn(
        architectPanelClassName(),
        "p-4",
        isLoading === true && "pointer-events-none opacity-60",
      )}
      aria-busy={isLoading === true ? "true" : undefined}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-heading text-sm font-semibold tracking-tight">{title}</h2>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
        <div className="flex flex-wrap gap-1">
          <Button variant="outline" size="sm" type="button" onClick={onOpenFilterDialog}>
            Filter dialog…
          </Button>
          <Button variant="secondary" size="sm" type="button" onClick={onInsertRow}>
            Insert row
          </Button>
          <Button
            variant="destructive"
            size="sm"
            type="button"
            disabled={deleteSelectedDisabled}
            onClick={onDeleteSelected}
          >
            <Trash2 className="size-3.5" />
            Delete selected
          </Button>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[640px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="w-10 px-2 py-2">
                <input
                  ref={selectAllCheckboxRef}
                  type="checkbox"
                  className="size-4 rounded border border-input accent-primary"
                  checked={allVisibleSelected}
                  onChange={onToggleSelectAllVisible}
                  aria-label="Select all visible rows"
                />
              </th>
              <th className="w-10 px-1 py-2" aria-label="Expand" />
              {TABLE_COLUMNS.map(({ key, label }) => (
                <th key={key} className="px-3 py-2 font-medium">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-md px-1 py-0.5 hover:bg-accent hover:text-accent-foreground"
                    onClick={() => onSort(key)}
                  >
                    {label}
                    {sortIndicator(key)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const expanded = expandedRowId === row.id;
              return (
                <Fragment key={row.id}>
                  <tr className="border-b border-border odd:bg-muted/20 hover:bg-muted/40">
                    <td className="px-2 py-2 align-middle">
                      <input
                        type="checkbox"
                        className="size-4 rounded border border-input accent-primary"
                        checked={selectedIds.has(row.id)}
                        onChange={() => onToggleRow(row.id)}
                        aria-label={`Select ${row.memberName}`}
                      />
                    </td>
                    <td className="px-1 py-2 align-middle">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        type="button"
                        aria-expanded={expanded}
                        onClick={() =>
                          onExpandedRowChange(expanded ? undefined : row.id)
                        }
                      >
                        {expanded ? (
                          <ChevronDown className="size-4" />
                        ) : (
                          <ChevronRight className="size-4" />
                        )}
                      </Button>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{row.caseId}</td>
                    <td className="px-3 py-2">{row.memberName}</td>
                    <td className="px-3 py-2">{row.program}</td>
                    <td className="px-3 py-2">
                      <span
                        className={cn(
                          "inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-border",
                          row.status === "Active" &&
                            "bg-success/15 text-success dark:bg-success/20 dark:text-success-foreground",
                          row.status === "Pending" &&
                            "bg-info/15 text-info dark:bg-info/20 dark:text-info-foreground",
                          row.status === "On hold" &&
                            "bg-warning/15 text-warning dark:bg-warning/20 dark:text-warning-foreground",
                          row.status === "Closed" && "bg-muted text-muted-foreground",
                        )}
                      >
                        {row.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{row.nextReview}</td>
                  </tr>
                  {expanded ? (
                    <tr className="border-b border-border bg-muted/30">
                      <td colSpan={7} className="px-4 py-3 text-xs text-muted-foreground">
                        <span className="font-medium text-foreground">Detail: </span>
                        {row.detailNote}
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
