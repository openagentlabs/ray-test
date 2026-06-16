import type { NavItemDefinition } from "@/lib/types/nav-item-definition";

export class NavigationService {
  private static readonly instance: NavigationService = new NavigationService();

  private readonly mainNavigation: readonly NavItemDefinition[] = Object.freeze([
    {
      id: "dashboard",
      title: "Dashboard",
      href: "/pages/dashboard",
      groupTitle: "Workspace",
    },
    {
      id: "settings",
      title: "Settings",
      href: "/pages/settings",
      groupTitle: "Account",
    },
  ] satisfies NavItemDefinition[]);

  public static getInstance(): NavigationService {
    return NavigationService.instance;
  }

  public getMainNavigation(): readonly NavItemDefinition[] {
    return this.mainNavigation;
  }

  private constructor() {}
}
