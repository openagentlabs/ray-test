import type { ReactNode } from "react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { NavigationService } from "@/lib/navigation/navigation-service";

export default function PagesWorkspaceLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  const navigationItems = NavigationService.getInstance().getMainNavigation();

  return (
    <DashboardShell navigationItems={navigationItems}>
      {children}
    </DashboardShell>
  );
}
