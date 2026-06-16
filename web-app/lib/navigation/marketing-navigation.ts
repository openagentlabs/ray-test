import type { NavItemDefinition } from "@/lib/types/nav-item-definition";

export class MarketingNavigation {
  private static readonly items: readonly NavItemDefinition[] = Object.freeze([
    { id: "arb-process", title: "ARB process", href: "#arb-process" },
    { id: "ai-agents", title: "AI agents", href: "#ai-agents" },
    { id: "how-it-works", title: "How it works", href: "#how-it-works" },
    { id: "governance", title: "Governance", href: "#governance" },
  ] satisfies NavItemDefinition[]);

  public static getItems(): readonly NavItemDefinition[] {
    return MarketingNavigation.items;
  }

  private constructor() {}
}
