import Image from "next/image";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import type { FC } from "react";

import { MarketingPageShell } from "@/components/layout/marketing-page-shell";
import { buttonVariants } from "@/components/ui/button";
import type { NavItemDefinition } from "@/lib/types/nav-item-definition";
import { cn } from "@/lib/utils";
import { DECISION_AI_NAME } from "@/pages-components/shared/decision-ai-brand";

interface HomePageProps {
  readonly navigationItems: readonly NavItemDefinition[];
}

export function HomePage({ navigationItems }: HomePageProps) {
  return (
    <MarketingPageShell navigationItems={navigationItems} footer={<MarketingFooter />}>
      <Hero />
    </MarketingPageShell>
  );
}

const Hero: FC = () => {
  return (
    <section className="relative overflow-hidden border-b border-border">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_60%_at_50%_0%,oklch(from_var(--primary)_l_c_h_/_0.22),transparent_70%)]"
      />
      <div className="relative mx-auto flex w-full max-w-6xl flex-col items-center gap-6 px-4 py-20 text-center sm:px-6 sm:py-28 lg:px-8 xl:max-w-7xl">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/60 px-3 py-1 text-xs font-medium text-muted-foreground">
          <Sparkles className="size-3.5 text-primary" aria-hidden />
          AI-Powered Analytics Platform
        </span>
        <h1 className="text-balance text-4xl font-semibold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
          Transform Your Data into{" "}
          <span className="bg-gradient-to-br from-primary to-foreground bg-clip-text text-transparent">
            Actionable Intelligence
          </span>
        </h1>
        <p className="mx-auto max-w-3xl text-balance text-base leading-relaxed text-muted-foreground sm:text-lg">
          The most comprehensive analytics platform with AI-powered insights, synthetic data
          generation, and advanced modeling capabilities designed for modern businesses.
        </p>
        <Link
          href="/pages/user/sign-in"
          className={cn(buttonVariants({ variant: "default", size: "lg" }), "min-w-44")}
        >
          Sign in to start
        </Link>
      </div>
    </section>
  );
};

const MarketingFooter: FC = () => {
  return (
    <footer className="border-t border-border bg-background/60">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-3 px-4 py-6 text-xs text-muted-foreground sm:flex-row sm:px-6 lg:px-8 xl:max-w-7xl">
        <span className="inline-flex items-center gap-2">
          <Image
            src="/exl-logo.png"
            alt="EXL Service"
            width={1280}
            height={477}
            className="h-3.5 w-auto opacity-80"
          />
          <span>
            &copy; {new Date().getFullYear()} EXL Service · {DECISION_AI_NAME}
          </span>
        </span>
        <span className="font-mono text-[11px] uppercase tracking-wider">
          Preview build
        </span>
      </div>
    </footer>
  );
};
