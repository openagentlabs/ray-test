import type { LucideIcon } from "lucide-react";
import { DraftingCompass, LayoutDashboard, Mail } from "lucide-react";

/**
 * Maps sidebar nav item ids to icons; unknown ids fall back to {@link LayoutDashboard}.
 */
export class NavigationIconResolver {
  private static readonly icons: Readonly<Record<string, LucideIcon>> =
    Object.freeze({
      "users-invites": Mail,
      "users-architect": DraftingCompass,
    });

  public resolve(navId: string): LucideIcon {
    const icon = NavigationIconResolver.icons[navId];
    if (icon === undefined) {
      return LayoutDashboard;
    }
    return icon;
  }
}
