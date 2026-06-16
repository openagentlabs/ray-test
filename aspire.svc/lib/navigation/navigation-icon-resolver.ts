import type { LucideIcon } from "lucide-react";
import {
  Home,
  LayoutDashboard,
  Settings,
} from "lucide-react";

export class NavigationIconResolver {
  private static readonly icons: Readonly<Record<string, LucideIcon>> =
    Object.freeze({
      home: Home,
      dashboard: LayoutDashboard,
      settings: Settings,
    });

  public resolve(navId: string): LucideIcon {
    const icon = NavigationIconResolver.icons[navId];
    if (icon === undefined) {
      return LayoutDashboard;
    }
    return icon;
  }
}
