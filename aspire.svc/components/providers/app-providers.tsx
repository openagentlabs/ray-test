"use client";

import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";

import { TooltipProvider } from "@/components/ui/tooltip";

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
    >
      <TooltipProvider delay={0}>{children}</TooltipProvider>
    </ThemeProvider>
  );
}
