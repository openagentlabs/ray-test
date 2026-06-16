import type { ReactNode } from "react";

import { MarketingPageShell } from "@/components/layout/marketing-page-shell";
import { TemplatesHeaderTrailing } from "@/pages-components/templates/components/templates-header-trailing";

export default function TemplatesRouteLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <MarketingPageShell headerTrailing={<TemplatesHeaderTrailing />}>
      {children}
    </MarketingPageShell>
  );
}
