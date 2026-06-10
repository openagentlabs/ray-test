import type { ReactNode } from "react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { getAspirePeopleAndArchitectNavigation } from "@/lib/navigation/aspire-pages-navigation";

export default function AspirePagesLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  const navigationItems = getAspirePeopleAndArchitectNavigation();

  return (
    <DashboardShell navigationItems={navigationItems}>{children}</DashboardShell>
  );
}
