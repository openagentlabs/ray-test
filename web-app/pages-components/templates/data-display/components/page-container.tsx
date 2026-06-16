"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { buttonVariants } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import {
  CodeDemoSection,
  TemplatePageShell,
} from "@/pages-components/templates/components/template-demo-kit";

export function DataDisplayTemplatePageContainer() {
  return (
    <TemplatePageShell
      title="Data display"
      description="Avatars identify people and workspaces; tooltips add lightweight context without modal interruption."
    >
      <CodeDemoSection
        title="Avatar sizes & fallback"
        description="Image avatars degrade gracefully to initials when photos are unavailable."
        preview={
          <div className="flex flex-wrap items-center gap-4">
            <Avatar className="size-8">
              <AvatarImage src="/exl-logo.png" alt="EXL logo avatar" />
              <AvatarFallback>EX</AvatarFallback>
            </Avatar>
            <Avatar className="size-10">
              <AvatarFallback>KR</AvatarFallback>
            </Avatar>
            <Avatar className="size-12">
              <AvatarFallback className="text-sm">DA</AvatarFallback>
            </Avatar>
          </div>
        }
        code={`<Avatar className="size-10">
  <AvatarImage src="/exl-logo.png" alt="EXL logo avatar" />
  <AvatarFallback>EX</AvatarFallback>
</Avatar>`}
      />

      <CodeDemoSection
        title="Tooltip placements"
        description="Use for icon-only controls; keep copy short and actionable."
        preview={
          <TooltipProvider>
            <div className="flex flex-wrap gap-3">
              <Tooltip>
                <TooltipTrigger
                  className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                >
                  Hover top
                </TooltipTrigger>
                <TooltipContent side="top">Export CSV snapshot</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger
                  className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                >
                  Hover bottom
                </TooltipTrigger>
                <TooltipContent side="bottom">Schedule recurring report</TooltipContent>
              </Tooltip>
            </div>
          </TooltipProvider>
        }
        code={`<TooltipProvider>
  <Tooltip>
    <TooltipTrigger asChild>
      <Button variant="outline">Hover top</Button>
    </TooltipTrigger>
    <TooltipContent side="top">Export CSV snapshot</TooltipContent>
  </Tooltip>
</TooltipProvider>`}
      />
    </TemplatePageShell>
  );
}
