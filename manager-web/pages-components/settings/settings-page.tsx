export function SettingsPage() {
  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Settings
        </h1>
        <p className="text-sm text-muted-foreground">
          Account and appearance preferences.
        </p>
      </header>
      <article className="rounded-xl border border-border bg-card p-6 shadow-surface">
        <p className="text-sm text-muted-foreground">
          Use the appearance control in the top header to switch between light and
          dark themes.
        </p>
      </article>
    </section>
  );
}
