import {
  ArrowRight,
  Bot,
  Braces,
  ClipboardList,
  DraftingCompass,
  Network,
  Scale,
  ServerCog,
  ShieldAlert,
  Sparkles,
  UserRound,
  Users,
  Workflow,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { FC, ReactNode } from "react";

import { buttonVariants } from "@/components/ui/button";
import { AppPublicConfig } from "@/lib/config/app-config-public";
import type { NavItemDefinition } from "@/lib/types/nav-item-definition";
import { cn } from "@/lib/utils";

interface HomePageProps {
  readonly navigationItems: readonly NavItemDefinition[];
}

export function HomePage({ navigationItems }: HomePageProps) {
  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <MarketingHeader navigationItems={navigationItems} />
      <main className="flex flex-1 flex-col">
        <Hero />
        <TrustStrip />
        <ArbProcessSection />
        <FeatureGrid />
        <HowItWorks />
        <GovernanceSection />
        <CallToAction />
      </main>
      <MarketingFooter />
    </div>
  );
}

interface MarketingHeaderProps {
  readonly navigationItems: readonly NavItemDefinition[];
}

const MarketingHeader: FC<MarketingHeaderProps> = ({ navigationItems }) => {
  return (
    <header className="sticky top-0 z-10 w-full border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-6 px-4 sm:px-6">
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

        <nav
          aria-label="Marketing navigation"
          className="hidden flex-1 items-center justify-center gap-1 md:flex"
        >
          {navigationItems.map((item) => (
            <Link
              key={item.id}
              href={item.href}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {item.title}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2 md:ml-0">
          <Link
            href="/login"
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
          >
            Log in
          </Link>
          <Link
            href="/register"
            className={cn(buttonVariants({ variant: "default", size: "sm" }))}
          >
            Register
          </Link>
        </div>
      </div>
    </header>
  );
};

interface FeatureCardProps {
  readonly icon: ReactNode;
  readonly title: string;
  readonly description: string;
  readonly ctaLabel: string;
  readonly ctaHref?: string | null;
}

const FeatureCard: FC<FeatureCardProps> = ({
  icon,
  title,
  description,
  ctaLabel,
  ctaHref,
}) => {
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
      <p className="flex-1 text-sm leading-relaxed text-muted-foreground">{description}</p>
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
};

const HERO_ROLE_START_ITEMS = Object.freeze([
  {
    id: "solution-owner",
    title: "Solution owner",
    description:
      "Kick off an ARB engagement: capture scope, stakeholders, and artefacts so the board can pick up structured intake.",
    icon: <UserRound className="size-5" aria-hidden />,
    ctaLabel: "Register solution",
    ctaHref: "/pages/solution-owner/register-solution-for-review" as const,
  },
  {
    id: "architect-reviewer",
    title: "Architect reviewer",
    description:
      "Review proposals against reference architectures and standards — trade-offs, ADRs, and sign-off in one place.",
    icon: <DraftingCompass className="size-5" aria-hidden />,
    ctaLabel: "Start here",
    ctaHref: null,
  },
  {
    id: "software-developer",
    title: "Software developer",
    description:
      "See implementation expectations, interfaces, and constraints flowing from the approved design and decision log.",
    icon: <Braces className="size-5" aria-hidden />,
    ctaLabel: "Start here",
    ctaHref: null,
  },
  {
    id: "devops",
    title: "DevOps",
    description:
      "Operational readiness, environments, pipelines, and runbooks aligned with the architecture and governance bar.",
    icon: <ServerCog className="size-5" aria-hidden />,
    ctaLabel: "Start here",
    ctaHref: null,
  },
]);

const Hero: FC = () => {
  return (
    <section className="relative overflow-hidden border-b border-border">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_60%_at_50%_0%,oklch(from_var(--primary)_l_c_h_/_0.22),transparent_70%)]"
      />
      <div className="relative mx-auto flex w-full max-w-6xl flex-col items-center gap-6 px-4 py-20 text-center sm:px-6 sm:py-28">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/60 px-3 py-1 text-xs font-medium text-muted-foreground">
          <Sparkles className="size-3.5 text-primary" aria-hidden />
          EXL Service · Architecture Review Board
        </span>
        <h1 className="text-balance text-4xl font-semibold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
          The EXLservice ARB - AI Assistant —{" "}
          <span className="bg-gradient-to-br from-primary to-foreground bg-clip-text text-transparent">
            the ARB process, assisted by AI agents
          </span>
          .
        </h1>
        <div className="mx-auto flex max-w-3xl flex-col gap-4 text-balance text-base leading-relaxed text-muted-foreground sm:text-lg">
          <p>
            Your starting point for Architecture Review at EXL Service. Register your solution,
            collaborate with your architect, and run intake, review, findings, and remediation in
            one place.
          </p>
          <p>
            AI agents scan your artefacts against EXL and industry standards as you build—so
            alignment keeps pace with every change, not just a one-time gate. Assessed templates
            and guided tools are built in.
          </p>
        </div>

        <div
          className="w-full max-w-6xl"
          role="region"
          aria-labelledby="hero-role-start-title"
        >
          <h2
            id="hero-role-start-title"
            className="mb-4 text-balance text-center text-lg font-semibold tracking-tight text-foreground sm:text-xl"
          >
            Start here by role
          </h2>
          <div className="grid w-full grid-cols-1 gap-4 text-left sm:grid-cols-2 lg:grid-cols-4">
            {HERO_ROLE_START_ITEMS.map((item) => (
              <FeatureCard
                key={item.id}
                icon={item.icon}
                title={item.title}
                description={item.description}
                ctaLabel={item.ctaLabel}
                ctaHref={item.ctaHref}
              />
            ))}
          </div>
        </div>

      </div>
    </section>
  );
};

interface TrustStat {
  readonly label: string;
  readonly value: string;
  readonly hint: string;
}

const TRUST_STATS: readonly TrustStat[] = Object.freeze([
  {
    label: "Time to first review",
    value: "Hours, not weeks",
    hint: "Agents draft the submission while you talk.",
  },
  {
    label: "Stakeholder coverage",
    value: "Product · Eng · Sec · Ops",
    hint: "Each role sees the slice of ARB that matters to them.",
  },
  {
    label: "Audit trail",
    value: "Every decision, traced",
    hint: "Versioned artefacts and ADRs linked to the SDD.",
  },
] satisfies TrustStat[]);

const TrustStrip: FC = () => {
  return (
    <section
      aria-label="Outcomes"
      className="border-b border-border bg-muted/30"
    >
      <div className="mx-auto grid w-full max-w-6xl grid-cols-1 gap-px overflow-hidden px-4 py-6 sm:grid-cols-3 sm:px-6">
        {TRUST_STATS.map((stat) => (
          <div
            key={stat.label}
            className="flex flex-col gap-1 px-4 py-3 text-left sm:px-6"
          >
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              {stat.label}
            </span>
            <span className="text-lg font-semibold tracking-tight text-foreground">
              {stat.value}
            </span>
            <span className="text-xs text-muted-foreground">{stat.hint}</span>
          </div>
        ))}
      </div>
    </section>
  );
};

const ArbProcessSection: FC = () => {
  return (
    <section
      id="arb-process"
      className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-20"
    >
      <div className="grid grid-cols-1 items-start gap-10 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-primary">
            The ARB process
          </span>
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            A guided path through Architecture Review — for every stakeholder.
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
            Solution and enterprise architects, security reviewers, engineering
            leads, and product owners each have a different stake in an ARB
            engagement. {AppPublicConfig.applicationName} routes the right work to
            the right reviewer and keeps the solution design document, ADRs,
            and decision log in lock-step with the conversation.
          </p>
          <ul className="mt-2 grid grid-cols-1 gap-2 text-sm text-muted-foreground sm:grid-cols-2">
            <ChecklistItem text="Stakeholder-aware intake" />
            <ChecklistItem text="Living solution design doc" />
            <ChecklistItem text="Traceable decisions & ADRs" />
            <ChecklistItem text="Security & risk woven in" />
          </ul>
        </div>

        <div className="relative rounded-2xl border border-border bg-card p-6 shadow-surface">
          <div
            aria-hidden
            className="pointer-events-none absolute -top-px left-6 right-6 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent"
          />
          <h3 className="text-sm font-semibold text-foreground">
            What an ARB engagement looks like here
          </h3>
          <ol className="mt-4 flex flex-col gap-3 text-sm text-muted-foreground">
            <ProcessRow
              n={1}
              title="Intake"
              detail="A copilot interviews the requester and drafts scope, context, and constraints."
            />
            <ProcessRow
              n={2}
              title="Discovery"
              detail="Agents pull standards, reference architectures, and prior decisions."
            />
            <ProcessRow
              n={3}
              title="Review"
              detail="Architecture, security, and operations agents review in parallel."
            />
            <ProcessRow
              n={4}
              title="Decision"
              detail="Human reviewers sign off; the SDD and decision log update together."
            />
          </ol>
        </div>
      </div>
    </section>
  );
};

interface ChecklistItemProps {
  readonly text: string;
}

const ChecklistItem: FC<ChecklistItemProps> = ({ text }) => {
  return (
    <li className="flex items-start gap-2">
      <span
        aria-hidden
        className="mt-1 inline-block size-1.5 shrink-0 rounded-full bg-primary"
      />
      <span>{text}</span>
    </li>
  );
};

interface ProcessRowProps {
  readonly n: number;
  readonly title: string;
  readonly detail: string;
}

const ProcessRow: FC<ProcessRowProps> = ({ n, title, detail }) => {
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
};

interface SpecializedAgentRow {
  readonly id: string;
  readonly title: string;
  readonly focus: string;
  readonly humanCheckpoint: string;
  readonly icon: ReactNode;
}

const SPECIALIZED_AGENTS: readonly SpecializedAgentRow[] = Object.freeze([
  {
    id: "intake-copilot",
    title: "Intake copilot",
    focus: "Structured stakeholder intake: scope, drivers, constraints, and artefacts in one draft.",
    humanCheckpoint: "You confirm or correct the draft before it becomes the working submission.",
    icon: <ClipboardList className="size-5" aria-hidden />,
  },
  {
    id: "architecture-reviewer",
    title: "Architecture reviewer",
    focus: "Reference architectures, standards, trade-offs, and gaps against the proposed design.",
    humanCheckpoint: "Architect reviewers interpret findings and decide what must change before sign-off.",
    icon: <DraftingCompass className="size-5" aria-hidden />,
  },
  {
    id: "security-risk",
    title: "Security and risk agent",
    focus: "Threat surfaces, controls, data handling, and operational risk woven into the same thread.",
    humanCheckpoint: "Security and risk owners weigh residual risk and approve compensating controls.",
    icon: <ShieldAlert className="size-5" aria-hidden />,
  },
  {
    id: "decision-keeper",
    title: "Decision keeper",
    focus: "Rationale, owners, follow-ups, and version links so the SDD and decision log stay aligned.",
    humanCheckpoint: "Material outcomes stay human-owned; the agent captures the record consistently.",
    icon: <Scale className="size-5" aria-hidden />,
  },
]);

const FeatureGrid: FC = () => {
  return (
    <section id="ai-agents" className="border-y border-border bg-muted/20">
      <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
        <div className="mb-10 flex flex-col gap-2 text-center">
          <span className="text-xs font-semibold uppercase tracking-wider text-primary">
            The AI assistant
          </span>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Specialised agents, working together under your oversight
          </h2>
          <p className="mx-auto max-w-2xl text-sm text-muted-foreground">
            {AppPublicConfig.applicationName} is an agentic workflow — not a single chatbot. The intake
            copilot, architecture reviewer, security and risk agent, and decision keeper each own part of
            the ARB process and collaborate with humans at the right checkpoints. The panels and table
            below summarise how they divide the work.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {SPECIALIZED_AGENTS.map((agent) => (
            <article
              key={agent.id}
              className="flex items-start gap-4 rounded-xl border border-border bg-card p-6 shadow-surface"
            >
              <span
                aria-hidden
                className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
              >
                {agent.icon}
              </span>
              <div className="flex min-w-0 flex-col gap-1.5">
                <h3 className="text-base font-semibold text-foreground">{agent.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{agent.focus}</p>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  <span className="font-medium text-foreground">Human checkpoint: </span>
                  {agent.humanCheckpoint}
                </p>
              </div>
            </article>
          ))}
        </div>

        <div className="mt-10 overflow-x-auto rounded-xl border border-border bg-card shadow-surface">
          <table className="w-full min-w-[720px] border-collapse text-left text-sm text-card-foreground">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="px-4 py-3 font-semibold">Agent</th>
                <th className="px-4 py-3 font-semibold">Focus</th>
                <th className="px-4 py-3 font-semibold">Human checkpoint</th>
              </tr>
            </thead>
            <tbody>
              {SPECIALIZED_AGENTS.map((agent) => (
                <tr key={`${agent.id}-row`} className="border-b border-border last:border-b-0">
                  <td className="align-top px-4 py-3">
                    <span className="inline-flex items-center gap-2 font-medium text-foreground">
                      <span
                        aria-hidden
                        className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"
                      >
                        {agent.icon}
                      </span>
                      {agent.title}
                    </span>
                  </td>
                  <td className="align-top px-4 py-3 text-muted-foreground">{agent.focus}</td>
                  <td className="align-top px-4 py-3 text-muted-foreground">{agent.humanCheckpoint}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
};

interface HowItWorksStep {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly icon: ReactNode;
}

const HOW_IT_WORKS_STEPS: readonly HowItWorksStep[] = Object.freeze([
  {
    id: "intake",
    title: "1. Stakeholder intake",
    description:
      "A requester opens a session. The copilot asks the right questions and assembles scope, drivers, and constraints into a draft submission.",
    icon: <ClipboardList className="size-5" />,
  },
  {
    id: "assemble",
    title: "2. Evidence assembly",
    description:
      "Agents pull EXL reference architectures, prior ADRs, and relevant standards. The solution design document is drafted in place.",
    icon: <Network className="size-5" />,
  },
  {
    id: "review",
    title: "3. Parallel AI review",
    description:
      "Architecture, security, and operations agents run in parallel, raising trade-offs and gaps for human reviewers to weigh in on.",
    icon: <Workflow className="size-5" />,
  },
  {
    id: "decide",
    title: "4. Human decision",
    description:
      "Reviewers approve, defer, or reject — with the rationale, owners, and follow-ups captured in the decision log automatically.",
    icon: <Users className="size-5" />,
  },
] satisfies HowItWorksStep[]);

const HowItWorks: FC = () => {
  return (
    <section
      id="how-it-works"
      className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-20"
    >
      <div className="mb-10 flex flex-col gap-2 text-center">
        <span className="text-xs font-semibold uppercase tracking-wider text-primary">
          How it works
        </span>
        <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          From request to signed-off architecture, in four guided steps
        </h2>
        <p className="mx-auto max-w-2xl text-sm text-muted-foreground">
          Humans stay in control at every checkpoint — the agents accelerate
          the work between them.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {HOW_IT_WORKS_STEPS.map((step) => (
          <article
            key={step.id}
            className="flex items-start gap-4 rounded-xl border border-border bg-card p-6 shadow-surface"
          >
            <span
              aria-hidden
              className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
            >
              {step.icon}
            </span>
            <div className="flex flex-col gap-1.5">
              <h3 className="text-base font-semibold text-foreground">
                {step.title}
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {step.description}
              </p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
};

const GovernanceSection: FC = () => {
  return (
    <section id="governance" className="border-y border-border bg-muted/20">
      <div className="mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-10 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-[1.1fr_1fr]">
        <div className="flex flex-col gap-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-primary">
            Governance built in
          </span>
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Agentic speed, ARB-grade accountability
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
            Every agent action is policy-bounded and auditable. Sensitive
            information stays inside EXL Service&apos;s trust boundary, human
            reviewers approve material decisions, and the resulting artefacts
            satisfy the same governance bar as a manual ARB.
          </p>
          <ul className="mt-1 grid grid-cols-1 gap-2 text-sm text-muted-foreground">
            <ChecklistItem text="Policy-bounded agents with explicit tool scopes" />
            <ChecklistItem text="Human-in-the-loop at every material decision" />
            <ChecklistItem text="Versioned SDD, ADRs, and decision log" />
            <ChecklistItem text="Zero-trust by default; least-privilege access" />
          </ul>
        </div>

        <div className="relative overflow-hidden rounded-2xl border border-border bg-card p-6 shadow-surface">
          <div
            aria-hidden
            className="pointer-events-none absolute -right-12 -top-12 size-48 rounded-full bg-primary/10 blur-3xl"
          />
          <div className="relative flex flex-col gap-4">
            <span className="inline-flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Bot className="size-5" aria-hidden />
            </span>
            <h3 className="text-base font-semibold text-foreground">
              One AI assistant. Many specialised agents.
            </h3>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {AppPublicConfig.applicationName} is the front door for ARB work at EXL
              Service. Stakeholders see one calm, conversational surface; under
              the hood, the right agent runs the right step — and a human owns
              the decision.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

const CallToAction: FC = () => {
  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
      <div className="relative overflow-hidden rounded-2xl border border-border bg-card p-8 text-center shadow-surface sm:p-12">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(80%_80%_at_50%_0%,oklch(from_var(--primary)_l_c_h_/_0.18),transparent_70%)]"
        />
        <div className="relative mx-auto flex max-w-2xl flex-col items-center gap-4">
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Bring your next architecture review to {AppPublicConfig.applicationName}
          </h2>
          <p className="text-sm text-muted-foreground sm:text-base">
            Replace ad-hoc submissions, scattered diagrams, and email-driven
            review loops with one guided agentic workflow.
          </p>
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:flex-wrap sm:justify-center">
            <Link
              href="/pages/solution-owner/register-solution-for-review"
              className={cn(
                buttonVariants({ variant: "default", size: "lg" }),
                "min-w-44 border-2 border-primary ring-2 ring-primary/20",
              )}
            >
              Register a solution
              <ArrowRight className="size-4" aria-hidden />
            </Link>
            <Link
              href="/register"
              className={cn(
                buttonVariants({ variant: "secondary", size: "lg" }),
                "min-w-44",
              )}
            >
              Get started
              <ArrowRight className="size-4" aria-hidden />
            </Link>
            <Link
              href="/login"
              className={cn(
                buttonVariants({ variant: "outline", size: "lg" }),
                "min-w-44",
              )}
            >
              I already have an account
            </Link>
          </div>
          <p className="text-xs text-muted-foreground sm:text-sm">
            <span className="font-medium text-foreground">Solution owners:</span> use{" "}
            <span className="font-medium text-foreground">Register a solution</span> to open the
            ARB intake form. Other roles can continue with Get started or Log in.
          </p>
        </div>
      </div>
    </section>
  );
};

const MarketingFooter: FC = () => {
  return (
    <footer className="border-t border-border bg-background/60">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-3 px-4 py-6 text-xs text-muted-foreground sm:flex-row sm:px-6">
        <span className="inline-flex items-center gap-2">
          <Image
            src="/exl-logo.png"
            alt="EXL Service"
            width={1280}
            height={477}
            className="h-3.5 w-auto opacity-80"
          />
          <span>
            &copy; {new Date().getFullYear()} EXL Service ·{" "}
            {AppPublicConfig.applicationName}
          </span>
        </span>
        <span className="font-mono text-[11px] uppercase tracking-wider">
          Preview build
        </span>
      </div>
    </footer>
  );
};
