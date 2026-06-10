import type { NavItemDefinition } from "@/lib/types/nav-item-definition";

export class NavigationService {
  private static instance: NavigationService | undefined;

  private readonly mainNavigation: readonly NavItemDefinition[];

  private constructor() {
    this.mainNavigation = Object.freeze([] satisfies NavItemDefinition[]);
  }

  public static getInstance(): NavigationService {
    if (NavigationService.instance === undefined) {
      NavigationService.instance = new NavigationService();
    }
    return NavigationService.instance;
  }

  public getMainNavigation(): readonly NavItemDefinition[] {
    return this.mainNavigation;
  }
}
