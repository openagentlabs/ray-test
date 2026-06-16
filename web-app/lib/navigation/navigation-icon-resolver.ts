import type { LucideIcon } from "lucide-react";
import {
  FolderOpen,
  Home,
  LayoutDashboard,
  Settings,
} from "lucide-react";

export class NavigationIconResolver {
  private static readonly icons: Readonly<Record<string, LucideIcon>> =
    Object.freeze({
      home: Home,
      dashboard: LayoutDashboard,
      documents: FolderOpen,
      settings: Settings,
    });

  public resolve(navId: string): LucideIcon {
    const icon: LucideIcon | undefined =
      NavigationIconResolver.icons[navId];
    if (icon === undefined) {
      return LayoutDashboard;
    }
    return icon;
  }
}
