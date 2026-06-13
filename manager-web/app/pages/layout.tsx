import type { ReactNode } from "react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { NavigationService } from "@/lib/navigation/navigation-service";
import type { NavItemDefinition } from "@/lib/types/nav-item-definition";

export default function PagesWorkspaceLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  const navigationItems: readonly NavItemDefinition[] =
    NavigationService.getInstance().getMainNavigation();

  return (
    <DashboardShell navigationItems={navigationItems}>
      {children}
    </DashboardShell>
  );
}
