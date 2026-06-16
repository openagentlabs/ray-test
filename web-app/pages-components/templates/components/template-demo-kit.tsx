"use client";

import { Check, Copy } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  TemplatesPageLayout,
} from "@/pages-components/templates/components/templates-page-layout";

interface CodeDemoSectionProps {
  readonly title: string;
  readonly description: string;
  readonly preview: ReactNode;
  readonly code: string;
}

export function CodeDemoSection({
  title,
  description,
  preview,
  code,
}: CodeDemoSectionProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <article className="overflow-hidden rounded-2xl border border-border bg-card text-card-foreground shadow-surface">
      <div className="border-b border-border px-4 py-4 sm:px-6 sm:py-5">
        <h3 className="text-base font-semibold text-foreground sm:text-lg">{title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{description}</p>
      </div>

      <div className="border-b border-border bg-muted/20 px-4 py-6 sm:px-6">{preview}</div>

      <Collapsible className="px-4 py-3 sm:px-6">
        <CollapsibleTrigger>View implementation</CollapsibleTrigger>
        <CollapsibleContent>
          <div className="relative overflow-hidden rounded-xl border border-border bg-muted/40">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="absolute top-3 right-3 z-10 bg-background/90"
              onClick={() => void handleCopy()}
            >
              {copied ? (
                <>
                  <Check className="size-4" aria-hidden />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="size-4" aria-hidden />
                  Copy snippet
                </>
              )}
            </Button>
            <pre className="overflow-x-auto p-4 pt-12 text-xs leading-relaxed text-foreground sm:text-sm">
              <code>{code.trim()}</code>
            </pre>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </article>
  );
}

interface TemplateGroupPageLayoutProps {
  readonly title: string;
  readonly description: string;
  readonly children: ReactNode;
}

export function TemplateGroupPageLayout({
  title,
  description,
  children,
}: TemplateGroupPageLayoutProps) {
  return (
    <TemplatesPageLayout
      eyebrow="Component templates"
      title={title}
      description={description}
      showBackLink
    >
      <div className="grid grid-cols-1 gap-6 xl:gap-8">{children}</div>
    </TemplatesPageLayout>
  );
}

/** @deprecated Use TemplateGroupPageLayout */
export const TemplatePageShell = TemplateGroupPageLayout;
