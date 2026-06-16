"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { FC, ReactNode } from "react";

import { TEMPLATES_INDEX_PATH } from "@/lib/templates/template-groups";

import { TemplatesIndexUrlBadge } from "./templates-index-url-badge";

interface TemplatesPageLayoutProps {
  readonly eyebrow: string;
  readonly title: string;
  readonly description: string;
  readonly children: ReactNode;
  readonly showBackLink?: boolean;
}

export const TemplatesPageLayout: FC<TemplatesPageLayoutProps> = ({
  eyebrow,
  title,
  description,
  children,
  showBackLink = false,
}) => {
  return (
    <section className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6 sm:py-10 md:py-12 lg:px-8 xl:max-w-7xl">
      {showBackLink ? (
        <nav aria-label="Template breadcrumb" className="flex flex-col gap-3">
          <Link
            href={TEMPLATES_INDEX_PATH}
            className="inline-flex w-fit items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Back to template gallery
          </Link>
          <TemplatesIndexUrlBadge className="w-fit lg:hidden" />
        </nav>
      ) : null}

      <header className="flex max-w-3xl flex-col gap-2 sm:gap-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-primary">
          {eyebrow}
        </p>
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl lg:text-4xl">
          {title}
        </h1>
        <p className="text-sm leading-relaxed text-muted-foreground sm:text-base lg:text-lg">
          {description}
        </p>
        {!showBackLink ? (
          <p className="text-xs text-muted-foreground">
            Share this gallery:{" "}
            <Link
              href={TEMPLATES_INDEX_PATH}
              className="font-mono text-foreground underline-offset-4 hover:text-primary hover:underline"
            >
              {TEMPLATES_INDEX_PATH}
            </Link>
          </p>
        ) : null}
      </header>

      {children}
    </section>
  );
};
