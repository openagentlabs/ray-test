import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  BadgeCheck,
  CircleCheck,
  Layers,
} from "lucide-react";

import type { ArchitectSolutionSummaryCounts } from "../architect-types";
import { architectPanelClassName } from "../architect-panel-styles";
import { cn } from "@/lib/utils";

export interface SolutionSummaryPanelsProps {
  readonly counts: ArchitectSolutionSummaryCounts;
}

interface SummaryPanelDefinition {
  readonly label: string;
  readonly valueKey: keyof ArchitectSolutionSummaryCounts;
  readonly hint: string;
  readonly accentBorder: string;
  readonly iconWrapper: string;
  readonly Icon: LucideIcon;
}

const PANEL_DEFINITIONS: readonly SummaryPanelDefinition[] = Object.freeze([
  {
    label: "ARB assigned",
    valueKey: "assignedToArchitect",
    hint: "Total solutions for ARB assigned to this architect",
    accentBorder: "border-t-primary",
    iconWrapper: "bg-primary/15 text-primary",
    Icon: Layers,
  },
  {
    label: "At risk",
    valueKey: "atRisk",
    hint: "Solutions needing architect focus and intervention",
    accentBorder: "border-t-warning",
    iconWrapper: "bg-warning/15 text-warning",
    Icon: AlertTriangle,
  },
  {
    label: "On track",
    valueKey: "onTrack",
    hint: "Total solutions currently on track",
    accentBorder: "border-t-success",
    iconWrapper: "bg-success/15 text-success dark:text-success-foreground",
    Icon: CircleCheck,
  },
  {
    label: "Completed",
    valueKey: "completed",
    hint: "Total solutions completed (mock aggregate)",
    accentBorder: "border-t-chart-2",
    iconWrapper: "bg-chart-2/15 text-chart-2",
    Icon: BadgeCheck,
  },
]);

export function SolutionSummaryPanels({ counts }: SolutionSummaryPanelsProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {PANEL_DEFINITIONS.map(
        ({ label, valueKey, hint, accentBorder, iconWrapper, Icon }) => (
          <div
            key={label}
            className={cn(
              architectPanelClassName(),
              "relative overflow-hidden",
              accentBorder,
              "border-t-[3px]",
            )}
          >
            <div className="p-4 pr-14">
              <p className="text-[0.65rem] font-semibold tracking-wide text-muted-foreground uppercase">
                {label}
              </p>
              <p className="mt-1 font-heading text-3xl font-semibold tracking-tight tabular-nums text-foreground">
                {counts[valueKey]}
              </p>
              <p className="mt-1 text-xs leading-snug text-muted-foreground">{hint}</p>
            </div>
            <div
              className={cn(
                "pointer-events-none absolute top-3 right-3 flex size-10 items-center justify-center rounded-full",
                iconWrapper,
              )}
              aria-hidden
            >
              <Icon className="size-5 shrink-0" strokeWidth={1.75} />
            </div>
          </div>
        ),
      )}
    </div>
  );
}
