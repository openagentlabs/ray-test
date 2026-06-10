"use client";

import { UserMenu } from "@/components/layout/user-menu";

import { UserProfilePlaceholder } from "@/lib/user/user-profile-placeholder";

export function AppHeader() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-end gap-2 border-b border-border bg-background/80 px-4 backdrop-blur-md sm:px-6">
      <UserMenu
        displayName={UserProfilePlaceholder.displayName}
        email={UserProfilePlaceholder.email}
      />
    </header>
  );
}
