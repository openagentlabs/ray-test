import type { ReactNode } from "react";

import { MarketingPageShell } from "@/components/layout/marketing-page-shell";

export default function UserPagesLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return <MarketingPageShell>{children}</MarketingPageShell>;
}
