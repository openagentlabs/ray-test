import { AppPublicConfig } from "@/lib/config/app-config-public";

export class SidebarPreferences {
  public static readCollapsed(): boolean {
    if (typeof window === "undefined") {
      return false;
    }
    return (
      window.localStorage.getItem(AppPublicConfig.sidebarStorageKey) === "true"
    );
  }

  public static writeCollapsed(collapsed: boolean): void {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(
      AppPublicConfig.sidebarStorageKey,
      collapsed ? "true" : "false",
    );
  }

  private constructor() {}
}
