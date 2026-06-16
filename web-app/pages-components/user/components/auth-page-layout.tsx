import type { FC, ReactNode } from "react";

interface AuthPageLayoutProps {
  readonly title: string;
  readonly description: string;
  readonly aside: ReactNode;
  readonly children: ReactNode;
  readonly footer: ReactNode;
}

export const AuthPageLayout: FC<AuthPageLayoutProps> = ({
  title,
  description,
  aside,
  children,
  footer,
}) => {
  return (
    <section className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 sm:px-6 sm:py-10 md:py-12 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:items-center lg:gap-12 lg:px-8 lg:py-16 xl:max-w-7xl xl:gap-16">
      <div className="hidden flex-col gap-4 lg:flex">
        {aside}
      </div>

      <div className="mx-auto flex w-full max-w-md flex-col gap-6 lg:mx-0 lg:max-w-none">
        <header className="flex flex-col gap-2 text-center lg:text-left">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            {title}
          </h1>
          <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
            {description}
          </p>
        </header>

        {children}

        <p className="text-center text-sm text-muted-foreground lg:text-left">{footer}</p>
      </div>
    </section>
  );
};

interface AuthPanelProps {
  readonly children: ReactNode;
}

export const AuthPanel: FC<AuthPanelProps> = ({ children }) => {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 text-card-foreground shadow-surface sm:p-6 md:p-8">
      {children}
    </div>
  );
};
