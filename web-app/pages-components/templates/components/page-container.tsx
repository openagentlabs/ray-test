import Link from "next/link";
import type { FC } from "react";

import { TEMPLATE_GROUPS } from "@/lib/templates/template-groups";
import { TemplatesPageLayout } from "@/pages-components/templates/components/templates-page-layout";

export const TemplatesPageContainer: FC = () => {
  return (
    <TemplatesPageLayout
      eyebrow="Design system"
      title="shadcn component templates for Decision.AI"
      description="Material-inspired panels map to grouped primitives styled with the EXL theme. Each group includes live previews, responsive layouts, and copy-ready snippets."
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {TEMPLATE_GROUPS.map((group) => (
          <Link
            key={group.id}
            href={group.href}
            className="group relative flex min-h-44 flex-col justify-between overflow-hidden rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-surface transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-surface-dropdown focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50 sm:p-6"
          >
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary/70 via-primary to-primary/40 opacity-80"
            />
            <div className="flex flex-col gap-2 pt-2">
              <h2 className="text-lg font-semibold tracking-tight text-foreground transition-colors group-hover:text-primary">
                {group.title}
              </h2>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {group.description}
              </p>
            </div>
            <p className="mt-4 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {group.componentCount} component
              {group.componentCount === 1 ? "" : "s"} · Open gallery
            </p>
          </Link>
        ))}
      </div>
    </TemplatesPageLayout>
  );
};
