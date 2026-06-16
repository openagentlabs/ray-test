export function DocumentsPage() {
  return (
    <section className="mx-auto flex w-full max-w-6xl flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Documents
        </h1>
        <p className="text-sm text-muted-foreground">
          Document storage management workspace.
        </p>
      </header>
      <article className="rounded-xl border border-border bg-card p-6 shadow-surface">
        <p className="text-sm text-muted-foreground">
          Connect document-storage service APIs here.
        </p>
      </article>
    </section>
  );
}
