"use client";

import * as React from "react";
import { Collapsible as CollapsiblePrimitive } from "@base-ui/react/collapsible";
import { ChevronDownIcon } from "lucide-react";

import { cn } from "@/lib/utils";

function Collapsible({ ...props }: Readonly<CollapsiblePrimitive.Root.Props>) {
  return <CollapsiblePrimitive.Root data-slot="collapsible" {...props} />;
}

function CollapsibleTrigger({
  className,
  children,
  ...props
}: Readonly<CollapsiblePrimitive.Trigger.Props>) {
  return (
    <CollapsiblePrimitive.Trigger
      data-slot="collapsible-trigger"
      className={cn(
        "group/collapsible-trigger flex w-full items-center justify-between gap-2 rounded-lg px-1 py-1 text-left text-sm font-medium text-foreground outline-none transition-colors hover:text-primary focus-visible:ring-3 focus-visible:ring-ring/50",
        className,
      )}
      {...props}
    >
      {children}
      <ChevronDownIcon
        aria-hidden
        className="size-4 shrink-0 text-muted-foreground transition-transform group-data-[panel-open]/collapsible-trigger:rotate-180"
      />
    </CollapsiblePrimitive.Trigger>
  );
}

function CollapsibleContent({
  className,
  children,
  ...props
}: Readonly<CollapsiblePrimitive.Panel.Props>) {
  return (
    <CollapsiblePrimitive.Panel
      data-slot="collapsible-content"
      className={cn(
        "overflow-hidden data-[closed]:animate-out data-[closed]:fade-out-0 data-[open]:animate-in data-[open]:fade-in-0",
        className,
      )}
      {...props}
    >
      <div className="pt-3">{children}</div>
    </CollapsiblePrimitive.Panel>
  );
}

export { Collapsible, CollapsibleContent, CollapsibleTrigger };
