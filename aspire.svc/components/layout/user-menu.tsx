"use client";

import { LogOut, Settings, User } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AnyhowResultFactory } from "@/lib/types/anyhow";
import { OptionValue, type Option } from "@/lib/types/option";
import { UserSessionClient } from "@/lib/user/session/user-session-client";
import { cn } from "@/lib/utils";

const ACCOUNT_SETTINGS_HREF = "/pages/settings";

interface UserMenuProps {
  readonly displayName: string;
  readonly email: string;
  readonly avatarUrl?: string;
}

export function UserMenu({ displayName, email, avatarUrl }: UserMenuProps) {
  const router = useRouter();
  const [isSigningOut, startSignOut] = useTransition();

  const handleSignOut = (): void => {
    startSignOut(() => {
      void UserSessionClient.getInstance()
        .signOut()
        .then((result) => {
          if (!result.ok) {
            console.error(AnyhowResultFactory.formatError(result.error));
            return;
          }
          router.push("/login");
          router.refresh();
        });
    });
  };

  const avatarOption: Option<string> = OptionValue.fromNullable(avatarUrl);

  const initials = displayName
    .split(" ")
    .map((part) => part.charAt(0))
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "rounded-full ring-offset-background outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        )}
      >
        <Avatar className="size-9">
          {avatarOption.some && avatarOption.value.length > 0 ? (
            <AvatarImage src={avatarOption.value} alt="" />
          ) : null}
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>
        <span className="sr-only">Open user menu</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel className="font-normal">
            <div className="flex flex-col space-y-0.5">
              <span className="text-sm font-medium text-foreground">
                {displayName}
              </span>
              <span className="text-xs text-muted-foreground">{email}</span>
            </div>
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem>
          <User className="size-4" />
          Profile
        </DropdownMenuItem>
        <DropdownMenuItem
          render={
            <Link
              href={ACCOUNT_SETTINGS_HREF}
              className="flex w-full items-center gap-1.5"
            />
          }
        >
          <Settings className="size-4" />
          Account settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          variant="destructive"
          disabled={isSigningOut}
          onClick={handleSignOut}
        >
          <LogOut className="size-4" />
          {isSigningOut ? "Signing out…" : "Log out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
