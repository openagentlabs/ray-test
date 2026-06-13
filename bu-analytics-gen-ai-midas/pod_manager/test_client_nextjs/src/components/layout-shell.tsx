import { AppShell } from "@/components/app-shell";
import { getSessionEmail } from "@/lib/session";

export async function LayoutShell({ children }: { children: React.ReactNode }) {
  const email = await getSessionEmail();
  return <AppShell email={email}>{children}</AppShell>;
}
