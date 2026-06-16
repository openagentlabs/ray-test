"use client";

import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { AppPublicConfig } from "@/lib/config/app-config-public";

interface AuthShellProps {
  readonly title: string;
  readonly description: string;
  readonly children: ReactNode;
  readonly footer: ReactNode;
}

export function AuthShell({
  title,
  description,
  children,
  footer,
}: AuthShellProps) {
  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <header className="border-b border-border bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center px-4 sm:px-6">
          <Link
            href="/"
            aria-label={`${AppPublicConfig.applicationName} — EXL Service`}
            className="inline-flex items-center gap-2.5 text-sm font-semibold tracking-tight text-foreground"
          >
            <Image
              src="/exl-logo.png"
              alt="EXL Service"
              width={1280}
              height={477}
              priority
              className="h-5 w-auto"
            />
            <span
              aria-hidden
              className="hidden h-4 w-px bg-border sm:inline-block"
            />
            <span className="hidden sm:inline-block">
              {AppPublicConfig.applicationName}
            </span>
          </Link>
        </div>
      </header>

      <main className="flex flex-1 items-center justify-center px-4 py-10 sm:px-6">
        <div className="w-full max-w-md">
          <div className="mb-6 flex flex-col gap-1 text-center">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {title}
            </h1>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-surface">
            {children}
          </div>
          <div className="mt-4 text-center text-sm text-muted-foreground">
            {footer}
          </div>
        </div>
      </main>
    </div>
  );
}
