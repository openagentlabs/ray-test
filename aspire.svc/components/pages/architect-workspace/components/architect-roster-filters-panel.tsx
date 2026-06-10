"use client";

import { ChevronDown, Search, X } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import { architectInputClassName, architectPanelClassName } from "../architect-panel-styles";

export interface ArchitectRosterKeywordFieldProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
}

export interface ArchitectRosterProgramTypeaheadProps {
  readonly query: string;
  readonly onQueryChange: (value: string) => void;
  readonly matches: readonly string[];
  readonly onSelectProgram: (program: string) => void;
  readonly onOpenLookup: () => void;
  /** Exact program filter sent to the workspace service (empty = no constraint). */
  readonly activeProgramExact: string;
  readonly onClearProgramFilter: () => void;
}

export interface ArchitectRosterStatusMultiSelectProps {
  readonly selected: readonly string[];
  readonly query: string;
  readonly onQueryChange: (value: string) => void;
  readonly pool: readonly string[];
  readonly onAdd: (status: string) => void;
  readonly onRemove: (status: string) => void;
}

export interface ArchitectRosterFiltersPanelProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly keyword: ArchitectRosterKeywordFieldProps;
  readonly programTypeahead: ArchitectRosterProgramTypeaheadProps;
  readonly statusMultiSelect: ArchitectRosterStatusMultiSelectProps;
}

export function ArchitectRosterFiltersPanel({
  open,
  onOpenChange,
  keyword,
  programTypeahead,
  statusMultiSelect,
}: ArchitectRosterFiltersPanelProps) {
  return (
    <Collapsible open={open} onOpenChange={onOpenChange}>
      <div id="advanced-filters" className={cn(architectPanelClassName(), "p-4")}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-heading text-sm font-semibold tracking-tight">
              Case roster filters
            </h2>
            <p className="text-xs text-muted-foreground">
              Mock layout — responsive 4 → 2 → 1 columns with consistent gutters.
            </p>
          </div>
          <CollapsibleTrigger
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              "inline-flex gap-1",
            )}
          >
            {open ? "Hide" : "Show"} criteria
            <ChevronDown
              className={cn(
                "size-3.5 transition-transform",
                open && "rotate-180",
              )}
            />
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent className="mt-4 data-[ending-style]:hidden">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="flex flex-col gap-1.5 sm:col-span-2 xl:col-span-2">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="kw">
                Keyword search
              </label>
              <div className="relative">
                <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <input
                  id="kw"
                  className={cn(architectInputClassName, "pl-8")}
                  placeholder="Filter roster as you type…"
                  value={keyword.value}
                  onChange={(e) => keyword.onChange(e.target.value)}
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5 xl:col-span-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-medium text-muted-foreground">Program</span>
                {programTypeahead.activeProgramExact.trim().length > 0 ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="xs"
                    className="h-6 text-xs"
                    onClick={programTypeahead.onClearProgramFilter}
                  >
                    Clear program filter
                  </Button>
                ) : null}
              </div>
              {programTypeahead.activeProgramExact.trim().length > 0 ? (
                <p className="text-xs text-muted-foreground">
                  Active filter:{" "}
                  <span className="font-medium text-foreground">
                    {programTypeahead.activeProgramExact}
                  </span>
                </p>
              ) : null}
              <div className="flex gap-1">
                <input
                  className={architectInputClassName}
                  aria-label="Program type-ahead"
                  value={programTypeahead.query}
                  onChange={(e) => programTypeahead.onQueryChange(e.target.value)}
                  placeholder="Type to narrow programs…"
                />
                <Tooltip>
                  <TooltipTrigger
                    render={
                      <Button
                        variant="outline"
                        size="icon-sm"
                        type="button"
                        onClick={programTypeahead.onOpenLookup}
                      >
                        <Search className="size-3.5" />
                      </Button>
                    }
                  />
                  <TooltipContent>Open lookup dialog</TooltipContent>
                </Tooltip>
              </div>
              {programTypeahead.query.trim().length > 0 ? (
                <ul
                  className="max-h-28 overflow-auto rounded-md border border-border bg-popover text-xs text-popover-foreground shadow-surface"
                  role="listbox"
                >
                  {programTypeahead.matches.map((opt) => (
                    <li key={opt}>
                      <button
                        type="button"
                        className="flex w-full px-2 py-1.5 text-left hover:bg-accent hover:text-accent-foreground"
                        onClick={() => programTypeahead.onSelectProgram(opt)}
                      >
                        {opt}
                      </button>
                    </li>
                  ))}
                  {programTypeahead.matches.length === 0 ? (
                    <li className="px-2 py-1.5 text-muted-foreground">No matches</li>
                  ) : null}
                </ul>
              ) : null}
            </div>
            <div className="flex flex-col gap-1.5 xl:col-span-1">
              <span className="text-xs font-medium text-muted-foreground">
                Status (multi-select mock)
              </span>
              <div
                className={cn(
                  "flex min-h-8 flex-wrap gap-1 rounded-md border border-input bg-background p-1.5",
                  "shadow-input",
                )}
              >
                {statusMultiSelect.selected.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-0.5 rounded-md bg-muted px-1.5 py-0.5 text-xs"
                  >
                    {tag}
                    <button
                      type="button"
                      className="rounded p-0.5 hover:bg-background"
                      aria-label={`Remove ${tag}`}
                      onClick={() => statusMultiSelect.onRemove(tag)}
                    >
                      <X className="size-3" />
                    </button>
                  </span>
                ))}
                <input
                  className="min-w-[6rem] flex-1 border-0 bg-transparent px-1 text-xs outline-none"
                  value={statusMultiSelect.query}
                  onChange={(e) => statusMultiSelect.onQueryChange(e.target.value)}
                  placeholder="Add status…"
                  aria-label="Add status filter"
                />
              </div>
              {statusMultiSelect.query.trim().length > 0 ? (
                <ul className="max-h-24 overflow-auto rounded-md border border-border bg-popover text-xs shadow-surface">
                  {statusMultiSelect.pool.map((s) => (
                    <li key={s}>
                      <button
                        type="button"
                        className="flex w-full px-2 py-1.5 text-left hover:bg-accent hover:text-accent-foreground"
                        onClick={() => statusMultiSelect.onAdd(s)}
                      >
                        {s}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
            <div className="flex flex-col gap-1 sm:col-span-2 xl:col-span-2">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="notes">
                Care team notes
              </label>
              <textarea
                id="notes"
                className={cn(architectInputClassName, "min-h-[4.5rem] py-2")}
                placeholder="Free text — validation messages would appear below in a vertical stack."
                defaultValue=""
              />
            </div>
            <div className="flex flex-col gap-1 sm:col-span-1 xl:col-span-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="city">
                City
              </label>
              <input id="city" className={architectInputClassName} placeholder="Springfield" />
            </div>
            <div className="flex flex-col gap-1 sm:col-span-1 xl:col-span-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="state">
                State
              </label>
              <input id="state" className={architectInputClassName} defaultValue="MO" />
            </div>
            <div className="flex max-w-full flex-col gap-1 sm:col-span-2 xl:col-span-1 xl:max-w-[7rem]">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="zip">
                ZIP
              </label>
              <input id="zip" className={architectInputClassName} placeholder="65807" />
            </div>
            <div className="flex flex-col gap-1 sm:col-span-2 xl:col-span-2">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-3">
                <div className="min-w-0 flex-1">
                  <label className="text-xs font-medium text-muted-foreground" htmlFor="mrn">
                    Member ID
                  </label>
                  <input id="mrn" className={architectInputClassName} placeholder="MRN-000000" />
                </div>
                <p className="text-xs text-muted-foreground sm:mt-5 sm:max-w-[40%]">
                  <span className="font-medium text-warning">Mock validation:</span>{" "}
                  in horizontal groups, helper text can sit to the right.
                </p>
              </div>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
