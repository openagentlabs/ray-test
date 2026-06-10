import { UserPlus } from "lucide-react";
import Link from "next/link";

import { architectPanelClassName } from "@/components/pages/architect-workspace/architect-panel-styles";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Full add-user flow uses {@code frontend/app/pages/admin/users/add/page.tsx} with IAM server actions.
 * This route gives Arb Aspire a real destination for the architect toolbar &quot;Add User&quot; control.
 */
export default function AspireUsersAddPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Add user</h1>
        <p className="text-muted-foreground">
          In the product workspace (frontend on port 8802), this flow creates users via the IAM service.
          Arb Aspire does not ship those server actions yet; use the frontend app for live user creation.
        </p>
      </div>
      <section
        className={cn(architectPanelClassName(), "border border-border p-5")}
        aria-labelledby="aspire-add-user-placeholder-title"
      >
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
          >
            <UserPlus className="size-5" />
          </span>
          <div className="min-w-0 space-y-3">
            <h2
              id="aspire-add-user-placeholder-title"
              className="text-base font-semibold tracking-tight text-foreground"
            >
              Add user (placeholder)
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              The product UI lives at{" "}
              <code className="rounded bg-muted px-1 font-mono text-xs">
                frontend/app/pages/admin/users/add/page.tsx
              </code>
              . To enable the same behaviour here, add the user-create actions and IAM client to this host.
            </p>
            <Link
              href="/pages/users/architect"
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "inline-flex w-fit")}
            >
              Back to architect workspace
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
