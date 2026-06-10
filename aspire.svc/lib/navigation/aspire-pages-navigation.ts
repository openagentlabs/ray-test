import type { NavItemDefinition } from "@/lib/types/nav-item-definition";

/**
 * Sidebar entries aligned with {@code frontend/lib/navigation/navigation-service.ts} for the
 * **People** and **Architect** groups from the repository’s initial import.
 * Aspire omits items that require next-auth, IAM gRPC, or other full-product wiring.
 */
export function getAspirePeopleAndArchitectNavigation(): readonly NavItemDefinition[] {
  return Object.freeze([
    {
      id: "users-invites",
      title: "Invites",
      href: "/pages/users/invites",
      groupTitle: "People",
    },
    {
      id: "users-architect",
      title: "Workspace",
      href: "/pages/users/architect",
      groupTitle: "Architect",
    },
  ]);
}
