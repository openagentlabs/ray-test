import {
  ArrowRight,
  Bot,
  Braces,
  DraftingCompass,
  Network,
  ServerCog,
  ShieldAlert,
  Sparkles,
  UserRound,
  Workflow,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { buttonVariants } from "@/components/ui/button";
import { AppPublicConfig } from "@/lib/config/app-config-public";
import { cn } from "@/lib/utils";

import {
  ChecklistItem,
  FeatureCard,
  ProcessRow,
} from "./marketing-primitives";

const HERO_ROLE_START_ITEMS = Object.freeze([
  {
    id: "software-developer",
    title: "Software developer",
    description:
      "Build your application with AI Smart Assistant at your side. Get help across design, implementation, and the infrastructure your code needs to run.",
    icon: <Braces className="size-5" aria-hidden />,
    ctaLabel: "Get started",
    ctaHref: "/register" as const,
  },
  {
    id: "devops",
    title: "DevOps",
    description:
      "Define the knowledge, standards, and processes that power AI Smart Infra Assistant so every deployment stays governed and secure.",
    icon: <ServerCog className="size-5" aria-hidden />,
    ctaLabel: "Start here",
    ctaHref: null,
  },
  {
    id: "solution-architect",
    title: "Solution architect",
    description:
      "Shape design and architecture choices with the developer. SmartInfra captures what the solution needs without Terraform or Helm templates.",
    icon: <DraftingCompass className="size-5" aria-hidden />,
    ctaLabel: "Start here",
    ctaHref: null,
  },
  {
    id: "platform-owner",
    title: "Platform owner",
    description:
      "Set governance, security, and EXL service domain rules so AI assistants deploy infrastructure that aligns with organisational policy.",
    icon: <UserRound className="size-5" aria-hidden />,
    ctaLabel: "Register",
    ctaHref: "/register" as const,
  },
]);

export function HeroSection() {
  return (
    <section className="relative overflow-hidden border-b border-border">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_60%_at_50%_0%,oklch(from_var(--primary)_l_c_h_/_0.22),transparent_70%)]"
      />
      <div className="relative mx-auto flex w-full max-w-6xl flex-col items-center gap-6 px-4 py-20 text-center sm:px-6 sm:py-28">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/60 px-3 py-1 text-xs font-medium text-muted-foreground">
          <Sparkles className="size-3.5 text-primary" aria-hidden />
          EXL Service · Developer platform
        </span>
        <h1 className="text-balance text-4xl font-semibold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
          {AppPublicConfig.applicationName}:{" "}
          <span className="bg-gradient-to-br from-primary to-foreground bg-clip-text text-transparent">
            AI that works with you while you build software
          </span>
          .
        </h1>
        <div className="mx-auto flex max-w-3xl flex-col gap-4 text-balance text-base leading-relaxed text-muted-foreground sm:text-lg">
          <p>
            Your companion through the development process. AI Smart Assistant helps you design,
            implement, and run applications with a range of specialised assistants tuned for
            real delivery work.
          </p>
          <p>
            Flagship capability: AI Smart Infra Assistant replaces the old world of Terraform
            templates, Helm charts, and shell scripts with a Python <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm text-foreground">infra</code> library
            and a live <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm text-foreground">SmartInfra</code> object
            that represents everything your application needs in the cloud.
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
}

interface TrustStat {
  readonly label: string;
  readonly value: string;
  readonly hint: string;
}

const TRUST_STATS: readonly TrustStat[] = Object.freeze([
  {
    label: "Infrastructure model",
    value: "Python SmartInfra",
    hint: "One object captures your full cloud footprint. No template sprawl.",
  },
  {
    label: "Pre-AI complexity",
    value: "Gone",
    hint: "No Terraform, Helm, or ad-hoc deploy scripts for the developer to maintain.",
  },
  {
    label: "Governance",
    value: "Built in",
    hint: "EXL domain knowledge, security, and policy enforced on every deployment.",
  },
]);

export function TrustStripSection() {
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
}

export function DeveloperAssistSection() {
  return (
    <section
      id="smart-assist"
      className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-20"
    >
      <div className="grid grid-cols-1 items-start gap-10 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-primary">
            From pre-AI to post-AI
          </span>
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Infrastructure without the old toolchain tax
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
            Before AI, developers depended on DevOps engineers for Terraform modules, Helm charts,
            scripts, and deep platform knowledge. AI Smart Infra Assistant changes that model.
            DevOps still owns standards and governance, but encodes them into the assistant so
            software developers interact with a simple, use-case-driven Python API.
          </p>
          <ul className="mt-2 grid grid-cols-1 gap-2 text-sm text-muted-foreground sm:grid-cols-2">
            <ChecklistItem text="Code-aware resource discovery" />
            <ChecklistItem text="Live SmartInfra view" />
            <ChecklistItem text="Real-time infra events" />
            <ChecklistItem text="Industry best-practice defaults" />
          </ul>
        </div>

        <div className="relative rounded-2xl border border-border bg-card p-6 shadow-surface">
          <div
            aria-hidden
            className="pointer-events-none absolute -top-px left-6 right-6 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent"
          />
          <h3 className="text-sm font-semibold text-foreground">
            How AI Smart Infra Assistant guides you
          </h3>
          <ol className="mt-4 flex flex-col gap-3 text-sm text-muted-foreground">
            <ProcessRow
              n={1}
              title="Analyze"
              detail="The assistant reads your application code and identifies the cloud resources your solution needs."
            />
            <ProcessRow
              n={2}
              title="Design"
              detail="You confirm architecture and design choices in conversation. No IaC literacy required."
            />
            <ProcessRow
              n={3}
              title="Model"
              detail="A Python infra library builds a SmartInfra object with properties that map to your use case."
            />
            <ProcessRow
              n={4}
              title="Align"
              detail="EXL governance, security, and service rules ensure what deploys matches organisational policy."
            />
          </ol>
        </div>
      </div>
    </section>
  );
}

interface SpecializedAgentRow {
  readonly id: string;
  readonly title: string;
  readonly focus: string;
  readonly humanCheckpoint: string;
  readonly icon: ReactNode;
}

const SPECIALIZED_AGENTS: readonly SpecializedAgentRow[] = Object.freeze([
  {
    id: "smart-assistant",
    title: "AI Smart Assistant",
    focus:
      "General development companion: design, coding, debugging, and delivery support across your application lifecycle.",
    humanCheckpoint:
      "You stay in control of every decision. The assistant accelerates the work between your choices.",
    icon: <Bot className="size-5" aria-hidden />,
  },
  {
    id: "smart-infra-assistant",
    title: "AI Smart Infra Assistant",
    focus:
      "End-to-end cloud infrastructure: analyze code, capture design intent, and model resources as a SmartInfra Python object.",
    humanCheckpoint:
      "You define what the application needs. The assistant handles platform complexity under EXL governance.",
    icon: <ServerCog className="size-5" aria-hidden />,
  },
  {
    id: "code-analyzer",
    title: "Code analyzer",
    focus:
      "Scans your solution codebase to infer databases, queues, storage, networking, and other resources required to run.",
    humanCheckpoint:
      "You validate findings and fill gaps the static analysis cannot see.",
    icon: <Braces className="size-5" aria-hidden />,
  },
  {
    id: "governance-security",
    title: "Governance and security",
    focus:
      "EXL service domain knowledge, security controls, and policy checks so deployed infrastructure stays compliant.",
    humanCheckpoint:
      "Platform and security owners set the rules. The assistant enforces them on every change.",
    icon: <ShieldAlert className="size-5" aria-hidden />,
  },
]);

export function FeatureGridSection() {
  return (
    <section id="ai-assistants" className="border-y border-border bg-muted/20">
      <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
        <div className="mb-10 flex flex-col gap-2 text-center">
          <span className="text-xs font-semibold uppercase tracking-wider text-primary">
            Specialised assistants
          </span>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            One platform, multiple AI assistants for development work
          </h2>
          <p className="mx-auto max-w-2xl text-sm text-muted-foreground">
            {AppPublicConfig.applicationName} is not a single chatbot. AI Smart Infra Assistant is
            the infrastructure flavour: it works with the Python <code className="rounded bg-muted px-1 font-mono text-xs text-foreground">infra</code> library
            so developers declare what they need through simple properties on a SmartInfra object,
            with a live view and real-time events from the running platform.
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
}

interface HowItWorksStep {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly icon: ReactNode;
}

const HOW_IT_WORKS_STEPS: readonly HowItWorksStep[] = Object.freeze([
  {
    id: "analyze",
    title: "1. Analyze your code",
    description:
      "AI Smart Infra Assistant inspects your application and proposes the cloud services, data stores, and integrations it needs.",
    icon: <Braces className="size-5" />,
  },
  {
    id: "design",
    title: "2. Capture design choices",
    description:
      "You work through architecture decisions in plain language. The assistant records them without asking you to write IaC.",
    icon: <DraftingCompass className="size-5" />,
  },
  {
    id: "model",
    title: "3. Build SmartInfra",
    description:
      "A Python infra object models your full footprint. Properties are use-case driven: you describe outcomes, not AWS primitives.",
    icon: <Network className="size-5" />,
  },
  {
    id: "run",
    title: "4. Deploy and observe",
    description:
      "Governed deployment with a live infrastructure view and real-time events so your app can react to what is happening in the cloud.",
    icon: <Workflow className="size-5" />,
  },
]);

export function HowItWorksSection() {
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
          From application code to governed cloud infrastructure in four steps
        </h2>
        <p className="mx-auto max-w-2xl text-sm text-muted-foreground">
          The developer leads. AI Smart Infra Assistant handles platform complexity under
          standards your DevOps team defines once.
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
}

export function GovernanceSection() {
  return (
    <section id="governance" className="border-y border-border bg-muted/20">
      <div className="mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-10 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-[1.1fr_1fr]">
        <div className="flex flex-col gap-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-primary">
            Governance built in
          </span>
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Smart infrastructure with enterprise-grade accountability
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
            AI Smart Infra Assistant carries EXL service domain knowledge, governance, and security
            requirements so what gets deployed is aligned with organisational policy. DevOps engineers
            codify standards into the platform; developers get a forward-leaning Python API instead
            of maintaining Terraform, Helm, or shell scripts.
          </p>
          <ul className="mt-1 grid grid-cols-1 gap-2 text-sm text-muted-foreground">
            <ChecklistItem text="100% aligned deployments under EXL policy" />
            <ChecklistItem text="No specialised infra knowledge on every property" />
            <ChecklistItem text="Industry best-practice defaults baked in" />
            <ChecklistItem text="Live SmartInfra view and real-time events" />
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
              SmartInfra: your application&apos;s infrastructure in one object
            </h3>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {AppPublicConfig.applicationName} is the entry point for developer assistance at EXL
              Service. Under the hood, AI Smart Infra Assistant builds and maintains a SmartInfra
              model that fully captures what your application needs to run: simple properties,
              governed outcomes, and no template archaeology.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

export function CallToActionSection() {
  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
      <div className="relative overflow-hidden rounded-2xl border border-border bg-card p-8 text-center shadow-surface sm:p-12">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(80%_80%_at_50%_0%,oklch(from_var(--primary)_l_c_h_/_0.18),transparent_70%)]"
        />
        <div className="relative mx-auto flex max-w-2xl flex-col items-center gap-4">
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Start building with {AppPublicConfig.applicationName}
          </h2>
          <p className="text-sm text-muted-foreground sm:text-base">
            Replace Terraform templates, Helm charts, and tribal DevOps knowledge with AI assistants
            that understand your code and model your infrastructure in Python.
          </p>
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:flex-wrap sm:justify-center">
            <Link
              href="/register"
              className={cn(
                buttonVariants({ variant: "default", size: "lg" }),
                "min-w-44 border-2 border-primary ring-2 ring-primary/20",
              )}
            >
              Create account
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
            <span className="font-medium text-foreground">Developers:</span> register to work with
            AI Smart Assistant and AI Smart Infra Assistant on your next application.
          </p>
        </div>
      </div>
    </section>
  );
}

export function MarketingFooterSection() {
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
}


