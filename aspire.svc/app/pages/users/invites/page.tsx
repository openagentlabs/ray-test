import { Mail } from "lucide-react";

import { architectPanelClassName } from "@/components/pages/architect-workspace/architect-panel-styles";
import { cn } from "@/lib/utils";

/**
 * Invites in the full product use {@code frontend/components/pages/invites/invites-admin-page.tsx}
 * with IAM-backed server actions. Aspire keeps this route so the People group matches the initial
 * layout; behaviour is documented here until the host wires the same services.
 */
export default function AspireUsersInvitesPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Invites</h1>
        <p className="text-muted-foreground">
          In the product workspace (frontend on port 8802), this area lists and manages email invites
          via the IAM service. Arb Aspire does not ship those server actions yet; use the frontend app
          for live invite administration.
        </p>
      </div>
      <section
        className={cn(architectPanelClassName(), "border border-border p-5")}
        aria-labelledby="aspire-invites-placeholder-title"
      >
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
          >
            <Mail className="size-5" />
          </span>
          <div className="min-w-0 space-y-2">
            <h2
              id="aspire-invites-placeholder-title"
              className="text-base font-semibold tracking-tight text-foreground"
            >
              Invite management (placeholder)
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              The initial repository import includes{" "}
              <code className="rounded bg-muted px-1 font-mono text-xs">
                frontend/app/pages/users/invites/page.tsx
              </code>{" "}
              backed by <code className="rounded bg-muted px-1 font-mono text-xs">InvitesAdminPage</code>.
              To enable the same behaviour here, add the invite actions and IAM client to this host.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
