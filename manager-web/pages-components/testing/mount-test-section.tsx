"use client";

import { Check, HardDrive, LoaderCircle, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AppPublicConfig } from "@/lib/config/app-config-public";
import type { SharedMountKind } from "@/lib/config/shared-mount-config";
import type {
  ClusterMountTestResult,
  ClusterTestStep,
  ClusterTestStepStatus,
} from "@/lib/cluster-testing/types";
import { cn } from "@/lib/utils";

export interface MountTestTarget {
  readonly kind: SharedMountKind;
  readonly volumeName: string;
  readonly mountPath: string;
  readonly displayName: string;
}

interface MountTestSectionProps {
  readonly target: MountTestTarget;
  readonly badge: string;
  readonly description: string;
}

export function MountTestSection({
  target,
  badge,
  description,
}: MountTestSectionProps) {
  const [result, setResult] = useState<ClusterMountTestResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const handleRunTest = async () => {
    setIsRunning(true);
    setResult(null);

    try {
      const response = await fetch("/api/cluster-testing/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mountKind: target.kind }),
      });

      if (!response.ok || response.body === null) {
        throw new Error(`Mount test request failed (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.trim().length === 0) {
            continue;
          }
          const snapshot = JSON.parse(line) as ClusterMountTestResult;
          setResult(snapshot);
        }
      }

      if (buffer.trim().length > 0) {
        const snapshot = JSON.parse(buffer) as ClusterMountTestResult;
        setResult(snapshot);
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Mount test failed unexpectedly";
      setResult({
        mountKind: target.kind,
        volumeName: target.volumeName,
        displayName: target.displayName,
        mountPath: target.mountPath,
        testFilePath: "",
        steps: createDefaultSteps(target.displayName).map((step) => ({
          ...step,
          status: "failure",
          detail: step.id === "validate-mount" ? message : "Step did not run",
        })),
        logs: [message],
        startedAt: new Date().toISOString(),
        completedAt: new Date().toISOString(),
        overallSuccess: false,
      });
    } finally {
      setIsRunning(false);
    }
  };

  const steps = result?.steps ?? createDefaultSteps(target.displayName);
  const displayedMountPath = result?.mountPath ?? target.mountPath;
  const displayedVolumeName = result?.volumeName ?? target.volumeName;

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-border bg-muted/60 px-3 py-1 text-xs font-medium text-muted-foreground">
          <HardDrive className="size-3.5 text-primary" aria-hidden />
          {badge}
        </span>
        <h2 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
          {target.displayName} testing
        </h2>
        <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
          {description}
        </p>
      </header>

      <article className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-surface">
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted/30 px-4 py-3">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Volume name
              </span>
              <code className="font-mono text-sm text-foreground">
                {displayedVolumeName}
              </code>
            </div>
            <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted/30 px-4 py-3">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Mount path
              </span>
              <code className="font-mono text-sm text-foreground">
                {displayedMountPath}
              </code>
            </div>
          </div>

          <Button
            type="button"
            size="lg"
            className="w-fit"
            disabled={isRunning}
            onClick={() => {
              void handleRunTest();
            }}
          >
            {isRunning ? (
              <>
                <LoaderCircle className="animate-spin" aria-hidden />
                Running test…
              </>
            ) : (
              "Test"
            )}
          </Button>
        </div>
      </article>

      <article className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-surface">
        <div className="mb-4 flex flex-col gap-1">
          <h3 className="text-base font-semibold text-foreground">Test steps</h3>
          <p className="text-sm text-muted-foreground">
            Each action updates as the run progresses. A check mark means the
            step succeeded; an X means it failed.
          </p>
        </div>

        <ol className="flex flex-col gap-3" aria-live="polite">
          {steps.map((step, index) => (
            <StepRow key={step.id} step={step} index={index + 1} />
          ))}
        </ol>

        {result !== null ? (
          <div className="mt-6 border-t border-border pt-4">
            <p
              className={cn(
                "text-sm font-medium",
                result.overallSuccess ? "text-success" : "text-destructive",
              )}
            >
              {result.overallSuccess
                ? `${target.displayName} mount test completed successfully.`
                : `${target.displayName} mount test failed. Expand the detailed log below for diagnostics.`}
            </p>
          </div>
        ) : null}
      </article>

      <Collapsible
        defaultOpen={false}
        className="rounded-xl border border-border bg-card p-6 shadow-surface"
      >
        <CollapsibleTrigger>
          <span className="text-base font-semibold text-foreground">
            Detailed test log
          </span>
          <span className="text-xs font-normal text-muted-foreground">
            {result === null
              ? "Hidden until a test run"
              : `${result.logs.length} entries`}
          </span>
        </CollapsibleTrigger>
        <CollapsibleContent>
          {result === null ? (
            <p className="text-sm text-muted-foreground">
              Run the test to populate timestamped log output from{" "}
              {AppPublicConfig.applicationName}.
            </p>
          ) : (
            <ScrollArea className="h-56 rounded-lg border border-border bg-muted/20">
              <pre className="p-4 font-mono text-xs leading-relaxed text-muted-foreground">
                {result.logs.join("\n")}
              </pre>
            </ScrollArea>
          )}
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}

function createDefaultSteps(displayName: string): readonly ClusterTestStep[] {
  return Object.freeze([
    {
      id: "validate-mount",
      label: `Validate ${displayName} mount point exists`,
      status: "pending",
    },
    {
      id: "open-file",
      label: `Open test file on ${displayName} mount`,
      status: "pending",
    },
    {
      id: "write-file",
      label: `Write 512 MB binary file to ${displayName} mount`,
      status: "pending",
    },
    {
      id: "close-file",
      label: "Close test file",
      status: "pending",
    },
    {
      id: "verify-file",
      label: "Verify written file size via Cluster client",
      status: "pending",
    },
    {
      id: "delete-file",
      label: `Delete test file from ${displayName} mount`,
      status: "pending",
    },
  ]);
}

interface StepRowProps {
  readonly step: ClusterTestStep;
  readonly index: number;
}

function StepRow({ step, index }: StepRowProps) {
  return (
    <li className="flex items-start gap-3 rounded-lg border border-border bg-background/60 px-4 py-3">
      <StepStatusIcon status={step.status} />
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="text-sm font-medium text-foreground">
          {index}. {step.label}
        </span>
        {step.detail !== undefined ? (
          <span className="text-xs leading-relaxed text-muted-foreground">
            {step.detail}
          </span>
        ) : null}
      </span>
    </li>
  );
}

interface StepStatusIconProps {
  readonly status: ClusterTestStepStatus;
}

function StepStatusIcon({ status }: StepStatusIconProps) {
  if (status === "running") {
    return (
      <span
        aria-label="Running"
        className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"
      >
        <LoaderCircle className="size-4 animate-spin" aria-hidden />
      </span>
    );
  }

  if (status === "success") {
    return (
      <span
        aria-label="Success"
        className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-success/15 text-success"
      >
        <Check className="size-4" aria-hidden />
      </span>
    );
  }

  if (status === "failure") {
    return (
      <span
        aria-label="Failed"
        className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-destructive/15 text-destructive"
      >
        <X className="size-4" aria-hidden />
      </span>
    );
  }

  return (
    <span
      aria-hidden
      className="mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground"
    >
      —
    </span>
  );
}
