import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppProviders } from "@/components/providers/app-providers";
import { AppPublicConfig } from "@/lib/config/app-config-public";

import "./globals.css";

export const metadata: Metadata = {
  title: AppPublicConfig.applicationName,
  description: `${AppPublicConfig.applicationName} manager web application`,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <body className="min-h-full bg-background text-foreground">
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
