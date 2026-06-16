"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import {
  CodeDemoSection,
  TemplatePageShell,
} from "@/pages-components/templates/components/template-demo-kit";

const SCROLL_ITEMS = Array.from({ length: 20 }, (_, index) => `Dataset row ${index + 1}`);

export function LayoutTemplatePageContainer() {
  return (
    <TemplatePageShell
      title="Layout & surfaces"
      description="Cards, dividers, collapsible sections, and scroll regions structure dense analytics content across breakpoints."
    >
      <CodeDemoSection
        title="Card composition"
        description="Header, content, and footer slots with EXL surface elevation."
        preview={
          <Card className="max-w-lg shadow-surface">
            <CardHeader>
              <CardTitle>Pipeline status</CardTitle>
              <CardDescription>Nightly feature engineering job</CardDescription>
            </CardHeader>
            <CardContent>
              Last run completed in 12m 04s with zero validation errors.
            </CardContent>
            <CardFooter className="justify-end gap-2">
              <Button variant="outline" size="sm">
                View logs
              </Button>
              <Button size="sm">Run again</Button>
            </CardFooter>
          </Card>
        }
        code={`<Card>
  <CardHeader>
    <CardTitle>Pipeline status</CardTitle>
    <CardDescription>Nightly feature engineering job</CardDescription>
  </CardHeader>
  <CardContent>Last run completed in 12m 04s.</CardContent>
  <CardFooter><Button size="sm">Run again</Button></CardFooter>
</Card>`}
      />

      <CodeDemoSection
        title="Separators"
        description="Horizontal and vertical dividers for list and toolbar grouping."
        preview={
          <div className="flex max-w-lg flex-col gap-4 rounded-xl border border-border p-4">
            <div className="flex items-center justify-between text-sm">
              <span>Accuracy</span>
              <span className="font-medium">92.4%</span>
            </div>
            <Separator />
            <div className="flex h-10 items-center gap-4 text-sm">
              <span>Train</span>
              <Separator orientation="vertical" />
              <span>Validate</span>
              <Separator orientation="vertical" />
              <span>Deploy</span>
            </div>
          </div>
        }
        code={`<Separator />
<Separator orientation="vertical" />`}
      />

      <CodeDemoSection
        title="Collapsible"
        description="Progressive disclosure for advanced configuration blocks."
        preview={
          <Collapsible className="max-w-lg rounded-xl border border-border p-4">
            <CollapsibleTrigger>Advanced model settings</CollapsibleTrigger>
            <CollapsibleContent>
              <p className="text-sm text-muted-foreground">
                Tune regularization, early stopping, and class weights without leaving the
                page.
              </p>
            </CollapsibleContent>
          </Collapsible>
        }
        code={`<Collapsible>
  <CollapsibleTrigger>Advanced model settings</CollapsibleTrigger>
  <CollapsibleContent>…</CollapsibleContent>
</Collapsible>`}
      />

      <CodeDemoSection
        title="Scroll area"
        description="Constrained lists on phone and tablet without breaking page layout."
        preview={
          <ScrollArea className="h-40 max-w-lg rounded-xl border border-border">
            <div className="flex flex-col gap-2 p-4">
              {SCROLL_ITEMS.map((item) => (
                <div
                  key={item}
                  className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm"
                >
                  {item}
                </div>
              ))}
            </div>
          </ScrollArea>
        }
        code={`<ScrollArea className="h-40 rounded-xl border">
  <div className="p-4">{rows}</div>
</ScrollArea>`}
      />
    </TemplatePageShell>
  );
}
