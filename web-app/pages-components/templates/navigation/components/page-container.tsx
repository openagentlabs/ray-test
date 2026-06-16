"use client";

import { LogOut, Settings, UserRound } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  CodeDemoSection,
  TemplatePageShell,
} from "@/pages-components/templates/components/template-demo-kit";

export function NavigationTemplatePageContainer() {
  return (
    <TemplatePageShell
      title="Navigation"
      description="Tabs organize peer content; dropdown menus collapse secondary actions without cluttering the layout."
    >
      <CodeDemoSection
        title="Tabs"
        description="Use for switching related views while preserving context on phone through desktop widths."
        preview={
          <Tabs defaultValue="overview" className="max-w-xl">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="models">Models</TabsTrigger>
              <TabsTrigger value="activity">Activity</TabsTrigger>
            </TabsList>
            <TabsContent value="overview" className="rounded-xl border border-border p-4">
              Portfolio health, latency, and usage summaries.
            </TabsContent>
            <TabsContent value="models" className="rounded-xl border border-border p-4">
              Registered models with version and owner metadata.
            </TabsContent>
            <TabsContent value="activity" className="rounded-xl border border-border p-4">
              Recent jobs, alerts, and collaborator actions.
            </TabsContent>
          </Tabs>
        }
        code={`<Tabs defaultValue="overview">
  <TabsList>
    <TabsTrigger value="overview">Overview</TabsTrigger>
    <TabsTrigger value="models">Models</TabsTrigger>
  </TabsList>
  <TabsContent value="overview">…</TabsContent>
</Tabs>`}
      />

      <CodeDemoSection
        title="Dropdown menu"
        description="Icon trigger with grouped commands and destructive action separated at the bottom."
        preview={
          <DropdownMenu>
            <DropdownMenuTrigger className={cn(buttonVariants({ variant: "outline" }))}>
              Account menu
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuLabel>Signed in as analyst</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem>
                <UserRound className="size-4" aria-hidden />
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Settings className="size-4" aria-hidden />
                Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive">
                <LogOut className="size-4" aria-hidden />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        }
        code={`<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button variant="outline">Account menu</Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent align="end">
    <DropdownMenuItem>Profile</DropdownMenuItem>
    <DropdownMenuItem variant="destructive">Sign out</DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>`}
      />
    </TemplatePageShell>
  );
}
