"use client";

import { useCallback, useEffect, useState } from "react";

import { getRegisteredServicesRuntimeSnapshot } from "@/app/actions/get-registered-services-runtime";
import { startRegisteredServiceById } from "@/app/actions/start-service-environment";
import { stopServiceEnvironment } from "@/app/actions/stop-service-environment";
import { getServices } from "@/app/actions/get-services";
import { Button } from "@/components/ui/button";
import type { AppInfo } from "@/lib/types/app-info";
import type { RegisteredServicesLoadResult } from "@/lib/types/registered-services-load-result";
import { cn } from "@/lib/utils";

import { architectPanelClassName } from "../architect-panel-styles";

const COL_COUNT = 16;

function formatJsonCell(value: string | null, maxLen: number): string {
  if (value === null || value.length === 0) {
    return "—";
  }
  if (value.length <= maxLen) {
    return value;
  }
  return `${value.slice(0, maxLen)}…`;
}

export function RegisteredServicesPanel({
  initialResult,
}: {
  readonly initialResult?: RegisteredServicesLoadResult;
}) {
  const [services, setServices] = useState<readonly AppInfo[] | undefined>(() =>
    initialResult?.ok === true ? initialResult.services : undefined,
  );
  const [error, setError] = useState<string | null>(() => {
    if (initialResult === undefined) {
      return null;
    }
    if (initialResult.ok) {
      return null;
    }
    return initialResult.detail !== undefined
      ? `${initialResult.message} (${initialResult.detail})`
      : initialResult.message;
  });
  const [pending, setPending] = useState(() => initialResult === undefined);
  const [runningById, setRunningById] = useState<Readonly<Record<string, boolean>>>({});
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [actionMessageById, setActionMessageById] = useState<
    Readonly<Record<string, string | undefined>>
  >({});

  const refreshRuntime = useCallback(async () => {
    const snap = await getRegisteredServicesRuntimeSnapshot();
    if (snap.ok) {
      setRunningById(snap.runningById);
      setRuntimeError(null);
    } else {
      setRuntimeError(
        snap.detail !== undefined ? `${snap.message} (${snap.detail})` : snap.message,
      );
    }
  }, []);

  useEffect(() => {
    if (initialResult !== undefined) {
      return;
    }
    let cancelled = false;
    void getServices()
      .then((result) => {
        if (cancelled) {
          return;
        }
        if (result.ok) {
          setServices(result.services);
          setError(null);
        } else {
          setServices(undefined);
          setError(
            result.detail !== undefined
              ? `${result.message} (${result.detail})`
              : result.message,
          );
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : "getServices failed.");
      })
      .finally(() => {
        if (!cancelled) {
          setPending(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [initialResult]);

  useEffect(() => {
    if (services === undefined || error !== null) {
      return;
    }
    queueMicrotask(() => {
      void refreshRuntime();
    });
    const t = window.setInterval(() => {
      void refreshRuntime();
    }, 5000);
    return () => window.clearInterval(t);
  }, [services, error, refreshRuntime]);

  async function handleStart(id: string): Promise<void> {
    setActionLoadingId(id);
    setActionMessageById((prev) => ({ ...prev, [id]: undefined }));
    const result = await startRegisteredServiceById(id);
    setActionLoadingId(null);
    if (result.ok) {
      setActionMessageById((prev) => ({ ...prev, [id]: "Start requested." }));
    } else {
      setActionMessageById((prev) => ({ ...prev, [id]: result.message }));
    }
    await refreshRuntime();
  }

  async function handleStop(id: string): Promise<void> {
    setActionLoadingId(id);
    setActionMessageById((prev) => ({ ...prev, [id]: undefined }));
    const result = await stopServiceEnvironment(id);
    setActionLoadingId(null);
    if (result.ok) {
      setActionMessageById((prev) => ({ ...prev, [id]: "Stop signaled." }));
    } else {
      setActionMessageById((prev) => ({ ...prev, [id]: result.message }));
    }
    await refreshRuntime();
  }

  return (
    <div
      className={cn(
        architectPanelClassName(),
        "p-4",
        pending && "pointer-events-none opacity-60",
      )}
      aria-busy={pending ? "true" : undefined}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-heading text-sm font-semibold tracking-tight">
            Registered services
          </h2>
          <p className="text-xs text-muted-foreground">
            Rows from the service registry SQLite file (same catalog as the booter CLI). The home
            route loads <span className="font-mono text-[11px]">AppInfo</span> rows on the server,
            including each row&apos;s resolved <span className="font-medium">workdir</span> path.
            Use <span className="font-medium">Start</span> / <span className="font-medium">Stop</span>{" "}
            to control processes tracked under{" "}
            <span className="font-mono text-[11px]">.aspire/booter-pids.json</span> and optional port
            probes.
          </p>
        </div>
      </div>

      {error !== null ? (
        <div
          className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          role="alert"
        >
          {error}
        </div>
      ) : null}

      {runtimeError !== null ? (
        <div
          className="mt-4 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-100"
          role="status"
        >
          {runtimeError}
        </div>
      ) : null}

      <div className="mt-4 overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[1880px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="px-3 py-2 font-medium">ID</th>
              <th className="px-3 py-2 font-medium">Display name</th>
              <th className="px-3 py-2 font-medium">Role</th>
              <th className="px-3 py-2 font-medium">Kind</th>
              <th className="px-3 py-2 font-medium">Workdir (rel.)</th>
              <th className="px-3 py-2 font-medium">Command</th>
              <th className="px-3 py-2 font-medium">Args (JSON)</th>
              <th className="px-3 py-2 font-medium">Port</th>
              <th className="px-3 py-2 font-medium">Health kind</th>
              <th className="px-3 py-2 font-medium">Health target</th>
              <th className="px-3 py-2 font-medium">Start order</th>
              <th className="px-3 py-2 font-medium">Enabled</th>
              <th className="px-3 py-2 font-medium">Auto @ home</th>
              <th className="px-3 py-2 font-medium">Description</th>
              <th className="px-3 py-2 font-medium">Env (JSON)</th>
              <th className="min-w-[200px] px-3 py-2 font-medium">Control</th>
            </tr>
          </thead>
          <tbody>
            {!pending && error === null && (services?.length ?? 0) === 0 ? (
              <tr>
                <td className="px-3 py-3 text-muted-foreground" colSpan={COL_COUNT}>
                  No registered services in the database yet.
                </td>
              </tr>
            ) : null}
            {(services ?? []).map((row) => {
              const running = runningById[row.id] === true;
              const busy = actionLoadingId === row.id;
              const hint = actionMessageById[row.id];
              return (
                <tr key={row.id} className="border-b border-border/80 last:border-0">
                  <td className="px-3 py-2 font-mono text-xs">{row.id}</td>
                  <td className="px-3 py-2">{row.displayName}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.role}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.kind}</td>
                  <td className="max-w-[140px] truncate px-3 py-2 font-mono text-xs text-muted-foreground">
                    <span title={`${row.workdirRelative}\n${row.workdirAbsolutePath}`}>
                      {row.workdirRelative}
                    </span>
                  </td>
                  <td className="max-w-[160px] truncate px-3 py-2 font-mono text-xs text-muted-foreground">
                    <span title={row.command}>{row.command}</span>
                  </td>
                  <td
                    className="max-w-[200px] truncate px-3 py-2 font-mono text-xs text-muted-foreground"
                    title={row.argsJson}
                  >
                    {formatJsonCell(row.argsJson, 48)}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {row.port === null ? "—" : String(row.port)}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{row.healthKind}</td>
                  <td className="max-w-[180px] truncate px-3 py-2 text-muted-foreground">
                    <span title={row.healthTarget ?? ""}>
                      {row.healthTarget === null || row.healthTarget.length === 0
                        ? "—"
                        : row.healthTarget}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{row.startOrder}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.enabled ? "yes" : "no"}</td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {row.autoStartWithHome ? "yes" : "no"}
                  </td>
                  <td className="max-w-[220px] truncate px-3 py-2 text-muted-foreground">
                    <span title={row.description}>{row.description}</span>
                  </td>
                  <td
                    className="max-w-[200px] truncate px-3 py-2 font-mono text-xs text-muted-foreground"
                    title={row.envJson ?? ""}
                  >
                    {formatJsonCell(row.envJson, 40)}
                  </td>
                  <td className="max-w-[220px] px-3 py-2 align-top text-xs">
                    {!row.enabled ? (
                      <span className="text-muted-foreground">—</span>
                    ) : (
                      <div className="flex flex-col gap-2">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <Button
                            type="button"
                            size="xs"
                            variant="default"
                            disabled={running || busy}
                            onClick={() => void handleStart(row.id)}
                          >
                            {busy && !running ? "Start…" : "Start"}
                          </Button>
                          <Button
                            type="button"
                            size="xs"
                            variant="destructive"
                            disabled={!running || busy}
                            onClick={() => void handleStop(row.id)}
                          >
                            {busy && running ? "Stop…" : "Stop"}
                          </Button>
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          {running ? "Appears running (PID file and/or port)." : "Appears stopped."}
                        </div>
                        {hint !== undefined ? (
                          <p
                            className={cn(
                              "text-[11px] leading-snug",
                              hint.startsWith("No Aspire") ||
                                hint.includes("Failed") ||
                                hint.includes("does not exist")
                                ? "text-destructive"
                                : "text-muted-foreground",
                            )}
                          >
                            {hint}
                          </p>
                        ) : null}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
