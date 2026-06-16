import Image from "next/image";
import Link from "next/link";
import type { FC, ReactNode } from "react";

import { buttonVariants } from "@/components/ui/button";
import type { NavItemDefinition } from "@/lib/types/nav-item-definition";
import { cn } from "@/lib/utils";
import { DECISION_AI_NAME } from "@/pages-components/shared/decision-ai-brand";

interface MarketingHeaderProps {
  readonly navigationItems?: readonly NavItemDefinition[];
  readonly trailing?: ReactNode;
  readonly showAuthActions?: boolean;
}

export const MarketingHeader: FC<MarketingHeaderProps> = ({
  navigationItems = [],
  trailing,
  showAuthActions = true,
}) => {
  const hasNavigation = navigationItems.length > 0;

  return (
    <header className="sticky top-0 z-(--z-header) w-full border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-4 px-4 sm:px-6 lg:px-8 xl:max-w-7xl">
        <Link
          href="/"
          aria-label={`${DECISION_AI_NAME} — EXL Service`}
          className="inline-flex min-w-0 shrink-0 items-center gap-2.5 text-foreground"
        >
          <Image
            src="/exl-logo.png"
            alt="EXL Service"
            width={1280}
            height={477}
            priority
            className="h-5 w-auto shrink-0"
          />
          <span
            aria-hidden
            className="hidden h-4 w-px shrink-0 bg-border sm:inline-block"
          />
          <span className="hidden truncate text-lg font-semibold tracking-tight sm:inline-block sm:text-xl">
            {DECISION_AI_NAME}
          </span>
        </Link>

        {hasNavigation ? (
          <nav
            aria-label="Marketing navigation"
            className="hidden flex-1 items-center justify-center gap-1 md:flex"
          >
            {navigationItems.map((item) => (
              <Link
                key={item.id}
                href={item.href}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {item.title}
              </Link>
            ))}
          </nav>
        ) : null}

        <div className="ml-auto flex min-w-0 shrink-0 items-center gap-2">
          {trailing}
          {showAuthActions ? (
            <>
              <Link
                href="/pages/user/sign-in"
                className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
              >
                Sign in
              </Link>
              <Link
                href="/pages/user/register"
                className={cn(buttonVariants({ variant: "default", size: "sm" }))}
              >
                Register
              </Link>
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
};
