"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
export function PageContainerDebug() {
  const [log, setLog] = useState<string>("");

  function append(line: string) {
    setLog((prev) => `${prev}${line}\n`);
  }

  async function run(label: string, fn: () => Promise<void>) {
    try {
      await fn();
      append(`OK ${label}`);
    } catch (e) {
      append(`ERR ${label}: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Debug console</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          onClick={() =>
            run("session", async () => {
              const r = await fetch("/api/session");
              append(JSON.stringify(await r.json()));
            })
          }
        >
          Session
        </Button>
        <Button
          variant="secondary"
          onClick={() =>
            run("availability", async () => {
              const r = await fetch("/api/lease/availability");
              append(JSON.stringify(await r.json()));
            })
          }
        >
          Pool availability
        </Button>
        <Button
          variant="secondary"
          onClick={() => run("acquire", async () => {
            const r = await fetch("/api/lease/acquire", { method: "POST" });
            append(`${r.status} ${JSON.stringify(await r.json())}`);
          })}
        >
          Acquire lease
        </Button>
        <Button
          variant="secondary"
          onClick={() => run("release", async () => {
            const r = await fetch("/api/lease/release", { method: "POST" });
            append(`${r.status} ${JSON.stringify(await r.json())}`);
          })}
        >
          Release lease
        </Button>
        <Button
          variant="secondary"
          onClick={() =>
            run("backend /api/v1/me", async () => {
              const { fetchBackendMe, formatBackendApiResult } = await import("@/lib/backend-api");
              append(formatBackendApiResult(await fetchBackendMe()));
            })
          }
        >
          Envoy /api/me
        </Button>
        <pre className="mt-4 w-full min-h-[200px] rounded-md bg-muted p-3 text-xs">{log}</pre>
      </CardContent>
    </Card>
  );
}
