import type { NavItemDefinition } from "@/lib/types/nav-item-definition";

export class MarketingNavigation {
  private static readonly items: readonly NavItemDefinition[] = Object.freeze([
    { id: "smart-assist", title: "Smart assist", href: "#smart-assist" },
    { id: "ai-assistants", title: "AI assistants", href: "#ai-assistants" },
    { id: "how-it-works", title: "How it works", href: "#how-it-works" },
    { id: "governance", title: "Governance", href: "#governance" },
  ] satisfies NavItemDefinition[]);

  public static getItems(): readonly NavItemDefinition[] {
    return MarketingNavigation.items;
  }

  private constructor() {}
}
