"use client";

import { Check, Copy } from "lucide-react";
import Link from "next/link";
import { useState, type FC } from "react";

import { TEMPLATES_INDEX_PATH } from "@/lib/templates/template-groups";
import { cn } from "@/lib/utils";

interface TemplatesIndexUrlBadgeProps {
  readonly className?: string;
}

export const TemplatesIndexUrlBadge: FC<TemplatesIndexUrlBadgeProps> = ({
  className,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (): Promise<void> => {
    const url =
      typeof window !== "undefined"
        ? `${window.location.origin}${TEMPLATES_INDEX_PATH}`
        : TEMPLATES_INDEX_PATH;

    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div
      className={cn(
        "inline-flex max-w-full items-center gap-2 rounded-lg border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground",
        className,
      )}
    >
      <span className="hidden font-medium md:inline">Gallery URL</span>
      <Link
        href={TEMPLATES_INDEX_PATH}
        className="truncate font-mono text-[11px] text-foreground underline-offset-4 hover:text-primary hover:underline sm:text-xs"
      >
        {TEMPLATES_INDEX_PATH}
      </Link>
      <button
        type="button"
        onClick={() => void handleCopy()}
        className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-background hover:text-foreground"
        aria-label="Copy template gallery URL"
      >
        {copied ? (
          <>
            <Check className="size-3.5" aria-hidden />
            Copied
          </>
        ) : (
          <>
            <Copy className="size-3.5" aria-hidden />
            Copy
          </>
        )}
      </button>
    </div>
  );
};
