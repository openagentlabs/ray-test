"use client";

import { ArrowRight, Loader2, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  CodeDemoSection,
  TemplatePageShell,
} from "@/pages-components/templates/components/template-demo-kit";

export function ButtonsTemplatePageContainer() {
  return (
    <TemplatePageShell
      title="Buttons"
      description="Action hierarchy follows Material guidance: one filled primary, supporting tonal actions, and destructive affordances only when necessary."
    >
      <CodeDemoSection
        title="Variants"
        description="Default, secondary, outline, ghost, destructive, and link treatments on the EXL primary palette."
        preview={
          <div className="flex flex-wrap gap-3">
            <Button>Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="link">Link</Button>
          </div>
        }
        code={`<Button>Primary</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="outline">Outline</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="destructive">Destructive</Button>
<Button variant="link">Link</Button>`}
      />

      <CodeDemoSection
        title="Sizes"
        description="Touch-friendly large buttons on phones; compact sizes for dense toolbars on laptop and desktop."
        preview={
          <div className="flex flex-wrap items-center gap-3">
            <Button size="lg">Large</Button>
            <Button>Default</Button>
            <Button size="sm">Small</Button>
            <Button size="xs">Extra small</Button>
            <Button size="icon" aria-label="Send email">
              <Mail aria-hidden />
            </Button>
          </div>
        }
        code={`<Button size="lg">Large</Button>
<Button>Default</Button>
<Button size="sm">Small</Button>
<Button size="xs">Extra small</Button>
<Button size="icon" aria-label="Send email">
  <Mail />
</Button>`}
      />

      <CodeDemoSection
        title="States"
        description="Loading and disabled states prevent duplicate submissions and communicate progress."
        preview={
          <div className="flex flex-wrap gap-3">
            <Button disabled>Disabled</Button>
            <Button disabled>
              <Loader2 className="size-4 animate-spin" aria-hidden />
              Loading
            </Button>
            <Button>
              Continue
              <ArrowRight className="size-4" aria-hidden />
            </Button>
          </div>
        }
        code={`<Button disabled>Disabled</Button>
<Button disabled>
  <Loader2 className="size-4 animate-spin" />
  Loading
</Button>
<Button>
  Continue
  <ArrowRight className="size-4" />
</Button>`}
      />
    </TemplatePageShell>
  );
}
