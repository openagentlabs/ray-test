"use client";

import { useId, useState } from "react";

import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  CodeDemoSection,
  TemplatePageShell,
} from "@/pages-components/templates/components/template-demo-kit";

export function FormsTemplatePageContainer() {
  const emailId = useId();
  const notesId = useId();
  const [marketing, setMarketing] = useState(false);

  return (
    <TemplatePageShell
      title="Form controls"
      description="Filled inputs with persistent labels, helper text, and validation states aligned to Material form patterns."
    >
      <CodeDemoSection
        title="Text inputs"
        description="Email and password fields with placeholders, autocomplete hints, and invalid styling."
        preview={
          <div className="grid max-w-md grid-cols-1 gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor={emailId}>Work email</Label>
              <Input
                id={emailId}
                type="email"
                autoComplete="email"
                placeholder="name@company.com"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password-demo">Password</Label>
              <Input
                id="password-demo"
                type="password"
                autoComplete="current-password"
                aria-invalid
                defaultValue="short"
              />
              <p className="text-xs text-destructive">Use at least 8 characters.</p>
            </div>
          </div>
        }
        code={`<Label htmlFor="email">Work email</Label>
<Input id="email" type="email" autoComplete="email" placeholder="name@company.com" />

<Label htmlFor="password">Password</Label>
<Input id="password" type="password" aria-invalid defaultValue="short" />
<p className="text-xs text-destructive">Use at least 8 characters.</p>`}
      />

      <CodeDemoSection
        title="Checkbox & switch"
        description="Binary choices for consent and feature toggles with accessible labels."
        preview={
          <div className="flex max-w-md flex-col gap-4">
            <div className="flex items-center gap-2">
              <Checkbox id="terms-demo" defaultChecked />
              <Label htmlFor="terms-demo">I agree to the terms</Label>
            </div>
            <div className="flex items-center justify-between gap-4 rounded-xl border border-border p-4">
              <div>
                <Label htmlFor="marketing-demo">Product updates</Label>
                <p className="text-xs text-muted-foreground">
                  Email me about new analytics features.
                </p>
              </div>
              <Switch
                id="marketing-demo"
                checked={marketing}
                onCheckedChange={setMarketing}
              />
            </div>
          </div>
        }
        code={`const [marketing, setMarketing] = useState(false);

<Checkbox id="terms" defaultChecked />
<Label htmlFor="terms">I agree to the terms</Label>

<Switch id="marketing" checked={marketing} onCheckedChange={setMarketing} />`}
      />

      <CodeDemoSection
        title="Textarea"
        description="Multi-line input for notes with minimum height and focus ring."
        preview={
          <div className="max-w-md">
            <div className="flex flex-col gap-2">
              <Label htmlFor={notesId}>Implementation notes</Label>
              <Textarea
                id={notesId}
                placeholder="Describe constraints, integrations, or rollout plan…"
              />
            </div>
          </div>
        }
        code={`<Label htmlFor="notes">Implementation notes</Label>
<Textarea id="notes" placeholder="Describe constraints…" />`}
      />

      <CodeDemoSection
        title="Disabled controls"
        description="Muted fields communicate read-only or pending-permission states."
        preview={
          <div className="grid max-w-md grid-cols-1 gap-3">
            <Input disabled defaultValue="Read-only tenant ID" />
            <Textarea disabled defaultValue="Editing disabled until review completes." />
          </div>
        }
        code={`<Input disabled defaultValue="Read-only tenant ID" />
<Textarea disabled defaultValue="Editing disabled until review completes." />`}
      />
    </TemplatePageShell>
  );
}
