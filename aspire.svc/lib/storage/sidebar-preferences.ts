import { AppConfig } from "@/lib/config/app-config";

export class SidebarPreferences {
  public static readCollapsed(): boolean {
    if (typeof window === "undefined") {
      return false;
    }
    return window.localStorage.getItem(AppConfig.sidebarStorageKey) === "true";
  }

  public static writeCollapsed(collapsed: boolean): void {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(
      AppConfig.sidebarStorageKey,
      collapsed ? "true" : "false",
    );
  }

  private constructor() {}
}
