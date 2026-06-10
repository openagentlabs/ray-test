import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function AspireWorkspaceUserPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">User</h1>
        <p className="text-muted-foreground">
          Account overview and shortcuts. Add profile data and actions here when your user domain is
          wired up.
        </p>
      </div>
      <Link
        href="/pages/user/settings"
        className={cn(buttonVariants({ variant: "secondary" }), "w-fit")}
      >
        User settings
      </Link>
    </div>
  );
}
