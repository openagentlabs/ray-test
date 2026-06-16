"use client";

import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";
import { AppPublicConfig } from "@/lib/config/app-config-public";

interface AppProvidersProps {
  readonly children: ReactNode;
}

export function AppProviders({ children }: AppProvidersProps) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      disableTransitionOnChange
      storageKey={AppPublicConfig.themeStorageKey}
    >
      <TooltipProvider delay={0}>{children}</TooltipProvider>
    </ThemeProvider>
  );
}
