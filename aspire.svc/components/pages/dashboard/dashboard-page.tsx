import { AppPublicConfig } from "@/lib/config/app-config-public";

export function DashboardPage() {
  return (
    <section className="mx-auto flex w-full max-w-6xl flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          Dashboard
        </h1>
        <p className="text-sm text-muted-foreground sm:text-base">
          Welcome to {AppPublicConfig.applicationName} workspace.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <article className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-surface">
          <h2 className="text-base font-semibold text-foreground">Getting started</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Use the sidebar to open settings or return to the marketing home page.
          </p>
        </article>
        <article className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-surface">
          <h2 className="text-base font-semibold text-foreground">Settings</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Update account preferences and appearance (light / dark theme).
          </p>
        </article>
        <article className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-surface sm:col-span-2 xl:col-span-1">
          <h2 className="text-base font-semibold text-foreground">Responsive</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Layout adapts for phone, tablet, laptop, and desktop breakpoints.
          </p>
        </article>
      </div>
    </section>
  );
}
