"use client";

import { useEffect, useState } from "react";

import { ThemeToggle } from "@/components/layout/theme-toggle";
import { UserMenu } from "@/components/layout/user-menu";
import { UserSessionClient } from "@/lib/user/session/user-session-client";
import type { UserProfileView } from "@/lib/user/models/user-profile";

export function AppHeader() {
  const [profile, setProfile] = useState<UserProfileView | null>(null);

  useEffect(() => {
    void UserSessionClient.getInstance()
      .getCurrentSession()
      .then((session) => {
        setProfile(session);
      });
  }, []);

  return (
    <header className="flex h-14 shrink-0 items-center justify-end gap-2 border-b border-border bg-background/80 px-4 backdrop-blur-md sm:px-6">
      <ThemeToggle />
      {profile !== null ? (
        <UserMenu displayName={profile.displayName} email={profile.email} />
      ) : null}
    </header>
  );
}
