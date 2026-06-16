import type { NavItemDefinition } from "@/lib/types/nav-item-definition";

import { MarketingHeader } from "./components/marketing-header";
import {
  DeveloperAssistSection,
  CallToActionSection,
  FeatureGridSection,
  GovernanceSection,
  HeroSection,
  HowItWorksSection,
  MarketingFooterSection,
  TrustStripSection,
} from "./components/marketing-sections";

export interface HomePageProps {
  readonly navigationItems: readonly NavItemDefinition[];
}

export function HomePage({ navigationItems }: HomePageProps) {
  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <MarketingHeader navigationItems={navigationItems} />
      <main className="flex flex-1 flex-col">
        <HeroSection />
        <TrustStripSection />
        <DeveloperAssistSection />
        <FeatureGridSection />
        <HowItWorksSection />
        <GovernanceSection />
        <CallToActionSection />
      </main>
      <MarketingFooterSection />
    </div>
  );
}
