import type { ReactNode } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar } from "@/components/layout/app-sidebar";
import type { NavItemDefinition } from "@/lib/types/nav-item-definition";

interface DashboardShellProps {
  readonly navigationItems: readonly NavItemDefinition[];
  readonly children: ReactNode;
}

export function DashboardShell({
  navigationItems,
  children,
}: DashboardShellProps) {
  return (
    <div className="flex h-dvh w-full overflow-hidden bg-background text-foreground">
      <AppSidebar navigationItems={navigationItems} />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <AppHeader />
        <main className="flex min-h-0 flex-1 flex-col overflow-auto p-4 sm:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
