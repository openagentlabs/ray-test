import type { LucideIcon } from "lucide-react";
import {
  BriefcaseBusiness,
  Code2,
  PenLine,
  ServerCog,
  Shield,
} from "lucide-react";

import type { ArchitectIamRoleSummaryCounts } from "../architect-types";
import { architectPanelClassName } from "../architect-panel-styles";
import { cn } from "@/lib/utils";

export interface IamRoleSummaryPanelsProps {
  readonly counts: ArchitectIamRoleSummaryCounts;
}

interface RolePanelDefinition {
  readonly label: string;
  readonly valueKey: keyof ArchitectIamRoleSummaryCounts;
  readonly hint: string;
  readonly accentBorder: string;
  readonly iconWrapper: string;
  readonly Icon: LucideIcon;
}

const PANEL_DEFINITIONS: readonly RolePanelDefinition[] = Object.freeze([
  {
    label: "Admins",
    valueKey: "admins",
    hint: "Users with an admin-type role in IAM for this account",
    accentBorder: "border-t-chart-3",
    iconWrapper: "bg-chart-3/15 text-chart-3",
    Icon: Shield,
  },
  {
    label: "Solution owners",
    valueKey: "solutionOwners",
    hint: "IAM users mapped to solution owner roles",
    accentBorder: "border-t-primary",
    iconWrapper: "bg-primary/15 text-primary",
    Icon: BriefcaseBusiness,
  },
  {
    label: "Architects",
    valueKey: "architects",
    hint: "IAM users mapped to architect roles",
    accentBorder: "border-t-chart-4",
    iconWrapper: "bg-chart-4/15 text-chart-4",
    Icon: PenLine,
  },
  {
    label: "Software devs",
    valueKey: "softwareDevs",
    hint: "IAM users mapped to software developer roles",
    accentBorder: "border-t-success",
    iconWrapper: "bg-success/15 text-success dark:text-success-foreground",
    Icon: Code2,
  },
  {
    label: "DevOps",
    valueKey: "devops",
    hint: "IAM users mapped to DevOps roles",
    accentBorder: "border-t-chart-2",
    iconWrapper: "bg-chart-2/15 text-chart-2",
    Icon: ServerCog,
  },
]);

export function IamRoleSummaryPanels({ counts }: IamRoleSummaryPanelsProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
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
