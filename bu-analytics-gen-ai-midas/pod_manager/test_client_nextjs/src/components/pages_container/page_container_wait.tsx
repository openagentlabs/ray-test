"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const WAIT_SEC = 60;

export function PageContainerWait() {
  const router = useRouter();
  const [secondsLeft, setSecondsLeft] = useState(WAIT_SEC);
  const [status, setStatus] = useState("No backend lease available. Waiting…");

  const tryAcquire = useCallback(async () => {
    const availRes = await fetch("/api/lease/availability");
    const avail = await availRes.json();
    if (avail.hasCapacity) {
      const res = await fetch("/api/lease/acquire", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.ok) {
        router.push("/home");
        return true;
      }
    }
    return false;
  }, [router]);

  useEffect(() => {
    const tick = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          void tryAcquire().then((ok) => {
            if (!ok) setStatus("Still no lease. Checking again in 60s…");
          });
          return WAIT_SEC;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [tryAcquire]);

  return (
    <Card className="mx-auto max-w-md">
      <CardHeader>
        <CardTitle>Waiting for a lease</CardTitle>
        <CardDescription>{status}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-3xl font-mono tabular-nums">{secondsLeft}s</p>
        <Button variant="secondary" onClick={() => void tryAcquire()}>
          Try now
        </Button>
        <a
          href="/api/auth/logout"
          className="inline-flex h-8 w-full items-center justify-center rounded-lg border border-border px-3 text-sm"
        >
          Stop waiting (log out)
        </a>
      </CardContent>
    </Card>
  );
}
