import Link from "next/link";
import Image from "next/image";

import { buttonVariants } from "@/components/ui/button";
import { AppPublicConfig } from "@/lib/config/app-config-public";
import type { NavItemDefinition } from "@/lib/types/nav-item-definition";
import { cn } from "@/lib/utils";

interface MarketingHeaderProps {
  readonly navigationItems: readonly NavItemDefinition[];
}

export function MarketingHeader({ navigationItems }: MarketingHeaderProps) {
  return (
    <header className="sticky top-0 z-10 w-full border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link
          href="/"
          aria-label={`${AppPublicConfig.applicationName} — EXL Service`}
          className="inline-flex items-center gap-2.5 text-sm font-semibold tracking-tight text-foreground"
        >
          <Image
            src="/exl-logo.png"
            alt="EXL Service"
            width={1280}
            height={477}
            priority
            className="h-5 w-auto"
          />
          <span aria-hidden className="hidden h-4 w-px bg-border sm:inline-block" />
          <span className="hidden sm:inline-block">
            {AppPublicConfig.applicationName}
          </span>
        </Link>

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

        <div className="ml-auto flex items-center gap-2 md:ml-0">
          <Link
            href="/login"
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
          >
            Log in
          </Link>
          <Link
            href="/register"
            className={cn(buttonVariants({ variant: "default", size: "sm" }))}
          >
            Register
          </Link>
        </div>
      </div>
    </header>
  );
}
