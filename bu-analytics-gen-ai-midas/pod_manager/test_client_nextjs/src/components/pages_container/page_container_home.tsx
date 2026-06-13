"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  fetchBackendMe,
  formatBackendApiResult,
  isNoBackendLeaseError,
} from "@/lib/backend-api";

export function PageContainerHome() {
  const router = useRouter();
  const [apiResult, setApiResult] = useState<string>("");
  const [apiError, setApiError] = useState<string | null>(null);
  const [releasing, setReleasing] = useState(false);
  const [loading, setLoading] = useState(true);

  const callBackend = useCallback(async () => {
    setLoading(true);
    setApiError(null);
    const statusRes = await fetch("/api/lease/status");
    if (statusRes.status === 401) {
      router.replace("/");
      return;
    }
    const status = (await statusRes.json()) as { hasLease: boolean };
    if (!status.hasLease) {
      router.replace("/lease");
      return;
    }
    const result = await fetchBackendMe();
    setApiResult(formatBackendApiResult(result));
    if (!result.ok) {
      setApiError(result.message);
      if (isNoBackendLeaseError(result)) {
        router.replace("/lease");
      }
    }
    setLoading(false);
  }, [router]);

  useEffect(() => {
    void callBackend();
  }, [callBackend]);

  async function release() {
    setReleasing(true);
    await fetch("/api/lease/release", { method: "POST" });
    setReleasing(false);
    window.location.href = "/lease";
  }

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Leased backend</CardTitle>
          <CardDescription>
            Calls <code className="text-xs">GET /api/v1/me</code> on your exclusive pod via Envoy.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button onClick={() => void callBackend()} disabled={loading}>
            {loading ? "Calling…" : "GET /api/v1/me"}
          </Button>
          {apiError ? (
            <p className="text-sm text-destructive" role="alert">
              {apiError}
            </p>
          ) : null}
          <pre className="rounded-md bg-muted p-3 text-xs overflow-auto min-h-[4rem]">
            {apiResult || "…"}
          </pre>
          <Button variant="destructive" onClick={release} disabled={releasing}>
            {releasing ? "Releasing…" : "Release lease"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
