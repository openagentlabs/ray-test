import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

export function FeatureCard({
  icon,
  title,
  description,
  ctaLabel,
  ctaHref,
}: {
  readonly icon: ReactNode;
  readonly title: string;
  readonly description: string;
  readonly ctaLabel: string;
  readonly ctaHref?: string | null;
}) {
  const ctaClassName =
    "inline-flex items-center gap-1.5 text-sm font-semibold text-primary transition-colors hover:text-primary/90";

  return (
    <article className="flex h-full flex-col gap-3 rounded-xl border border-border bg-card p-6 text-card-foreground shadow-surface transition-colors hover:bg-accent/40">
      <span
        aria-hidden
        className="inline-flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary"
      >
        {icon}
      </span>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      <p className="flex-1 text-sm leading-relaxed text-muted-foreground">
        {description}
      </p>
      <div className="pt-1">
        {ctaHref ? (
          <Link href={ctaHref} className={ctaClassName}>
            {ctaLabel}
            <ArrowRight className="size-4 shrink-0" aria-hidden />
          </Link>
        ) : (
          <span
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-muted-foreground"
            aria-disabled
          >
            {ctaLabel}
            <ArrowRight className="size-4 shrink-0 opacity-60" aria-hidden />
          </span>
        )}
      </div>
    </article>
  );
}

export function ChecklistItem({ text }: { readonly text: string }) {
  return (
    <li className="flex items-start gap-2">
      <span
        aria-hidden
        className="mt-1 inline-block size-1.5 shrink-0 rounded-full bg-primary"
      />
      <span>{text}</span>
    </li>
  );
}

export function ProcessRow({
  n,
  title,
  detail,
}: {
  readonly n: number;
  readonly title: string;
  readonly detail: string;
}) {
  return (
    <li className="flex items-start gap-3">
      <span
        aria-hidden
        className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary"
      >
        {n}
      </span>
      <span className="flex flex-col gap-0.5">
        <span className="text-sm font-medium text-foreground">{title}</span>
        <span className="text-xs leading-relaxed text-muted-foreground">
          {detail}
        </span>
      </span>
    </li>
  );
}
