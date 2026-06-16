import type { FC, ReactNode } from "react";

import { MarketingHeader } from "@/components/layout/marketing-header";
import type { NavItemDefinition } from "@/lib/types/nav-item-definition";

interface MarketingPageShellProps {
  readonly children: ReactNode;
  readonly navigationItems?: readonly NavItemDefinition[];
  readonly headerTrailing?: ReactNode;
  readonly showAuthActions?: boolean;
  readonly footer?: ReactNode;
}

export const MarketingPageShell: FC<MarketingPageShellProps> = ({
  children,
  navigationItems,
  headerTrailing,
  showAuthActions = true,
  footer,
}) => {
  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <MarketingHeader
        navigationItems={navigationItems}
        trailing={headerTrailing}
        showAuthActions={showAuthActions}
      />
      <main className="flex flex-1 flex-col">{children}</main>
      {footer}
    </div>
  );
};
