"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  fetchBackendMe,
  formatBackendApiResult,
  isNoBackendLeaseError,
} from "@/lib/backend-api";

type LeaseStatus = {
  hasLease: boolean;
  lease?: { podId: string; podDns: string; assignmentEpoch: number };
};

export function PageContainerLease() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [statusLoading, setStatusLoading] = useState(true);
  const [leaseStatus, setLeaseStatus] = useState<LeaseStatus | null>(null);
  const [apiPreview, setApiPreview] = useState<string | null>(null);
  const [apiLoading, setApiLoading] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/lease/status");
        if (res.status === 401) {
          router.replace("/");
          return;
        }
        const data = (await res.json()) as LeaseStatus;
        setLeaseStatus(data);
      } catch {
        setMessage("Could not load lease status.");
      } finally {
        setStatusLoading(false);
      }
    })();
  }, [router]);

  async function tryBackendWithoutLease() {
    setApiLoading(true);
    setApiPreview(null);
    setMessage(null);
    const result = await fetchBackendMe();
    setApiPreview(formatBackendApiResult(result));
    if (isNoBackendLeaseError(result)) {
      setMessage("Expected: no backend lease yet. Acquire a lease to reach your pod.");
    } else if (!result.ok) {
      setMessage(result.message);
    } else {
      setMessage("Unexpected: API succeeded without acquiring a lease on this page.");
    }
    setApiLoading(false);
  }

  async function acquireOrResume() {
    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch("/api/lease/acquire", { method: "POST" });
      const data = (await res.json()) as {
        ok?: boolean;
        error?: string;
        message?: string;
        alreadyLeased?: boolean;
      };
      if (res.ok && data.ok) {
        router.push("/home");
        return;
      }
      if (data.error === "no_capacity") {
        router.push("/wait");
        return;
      }
      setMessage(data.message ?? "Acquire failed");
    } catch {
      setMessage("Request failed");
    } finally {
      setLoading(false);
    }
  }

  const hasLease = leaseStatus?.hasLease === true;
  const buttonLabel = hasLease ? "Resume session" : "Acquire lease";

  return (
    <div className="mx-auto max-w-md space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{hasLease ? "Resume backend session" : "Acquire backend lease"}</CardTitle>
          <CardDescription>
            {hasLease
              ? "You already hold a lease. Continue to your exclusive backend pod."
              : "Exclusive use of one backend pool pod when available."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {statusLoading ? (
            <p className="text-sm text-muted-foreground">Checking lease status…</p>
          ) : hasLease && leaseStatus?.lease ? (
            <p className="text-sm text-muted-foreground">
              Current pod: <code className="text-xs">{leaseStatus.lease.podId}</code>
            </p>
          ) : null}
          {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
          <Button onClick={acquireOrResume} disabled={loading || statusLoading} className="w-full">
            {loading ? "Working…" : buttonLabel}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Backend API (no lease)</CardTitle>
          <CardDescription>
            Try <code className="text-xs">GET /api/v1/me</code> before leasing — should return{" "}
            <code className="text-xs">no_backend_lease</code>.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button variant="secondary" onClick={() => void tryBackendWithoutLease()} disabled={apiLoading}>
            {apiLoading ? "Calling…" : "Try backend API"}
          </Button>
          {apiPreview ? (
            <pre className="rounded-md bg-muted p-3 text-xs overflow-auto">{apiPreview}</pre>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
