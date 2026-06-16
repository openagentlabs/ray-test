"use client";

import { AlertCircle, CircleCheck, Info, TriangleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  CodeDemoSection,
  TemplatePageShell,
} from "@/pages-components/templates/components/template-demo-kit";

export function FeedbackTemplatePageContainer() {
  return (
    <TemplatePageShell
      title="Feedback"
      description="Alerts and badges communicate system status with semantic theme tokens for success, warning, info, and error."
    >
      <CodeDemoSection
        title="Alert variants"
        description="Use concise titles, supporting copy, and icons for scannable status messaging."
        preview={
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Alert>
              <Info aria-hidden />
              <AlertTitle>Heads up</AlertTitle>
              <AlertDescription>
                Model training will run overnight in your selected region.
              </AlertDescription>
            </Alert>
            <Alert variant="success">
              <CircleCheck aria-hidden />
              <AlertTitle>Deployment complete</AlertTitle>
              <AlertDescription>Version 2.4.1 is live for all workspaces.</AlertDescription>
            </Alert>
            <Alert variant="warning">
              <TriangleAlert aria-hidden />
              <AlertTitle>Quota nearing limit</AlertTitle>
              <AlertDescription>
                You have used 85% of monthly inference credits.
              </AlertDescription>
            </Alert>
            <Alert variant="destructive">
              <AlertCircle aria-hidden />
              <AlertTitle>Action required</AlertTitle>
              <AlertDescription>
                API credentials expired. Rotate keys to restore pipelines.
              </AlertDescription>
            </Alert>
          </div>
        }
        code={`<Alert variant="success">
  <CircleCheck />
  <AlertTitle>Deployment complete</AlertTitle>
  <AlertDescription>Version 2.4.1 is live.</AlertDescription>
</Alert>`}
      />

      <CodeDemoSection
        title="Badge variants"
        description="Compact labels for counts, statuses, and metadata chips."
        preview={
          <div className="flex flex-wrap gap-2">
            <Badge>Default</Badge>
            <Badge variant="secondary">Secondary</Badge>
            <Badge variant="outline">Outline</Badge>
            <Badge variant="success">Success</Badge>
            <Badge variant="warning">Warning</Badge>
            <Badge variant="destructive">Error</Badge>
          </div>
        }
        code={`<Badge>Default</Badge>
<Badge variant="secondary">Secondary</Badge>
<Badge variant="outline">Outline</Badge>
<Badge variant="success">Success</Badge>
<Badge variant="warning">Warning</Badge>
<Badge variant="destructive">Error</Badge>`}
      />
    </TemplatePageShell>
  );
}
