import { cn } from "@/lib/utils";

/** Shared card / panel surface for the architect workspace mock. */
export function architectPanelClassName(className?: string): string {
  return cn(
    "rounded-[10px] border border-border bg-card text-card-foreground shadow-surface",
    className,
  );
}

/** Single-line controls in architect mock forms and dialogs. */
export const architectInputClassName = cn(
  "flex h-8 w-full min-w-0 rounded-md border border-input bg-background px-2.5 text-sm text-foreground shadow-input outline-none",
  "placeholder:text-muted-foreground",
  "focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50",
);
