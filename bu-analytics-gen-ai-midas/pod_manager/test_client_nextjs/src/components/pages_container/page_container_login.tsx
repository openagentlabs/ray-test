"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

async function resumeOrAcquireAfterLogin(router: ReturnType<typeof useRouter>): Promise<string | null> {
  const res = await fetch("/api/lease/acquire", { method: "POST" });
  const data = (await res.json()) as {
    ok?: boolean;
    error?: string;
    message?: string;
    alreadyLeased?: boolean;
  };
  if (res.ok && data.ok) {
    router.push("/home");
    return null;
  }
  if (data.error === "no_capacity") {
    router.push("/wait");
    return null;
  }
  return data.message ?? "Could not resume or acquire a backend lease.";
}

export function PageContainerLogin() {
  const router = useRouter();
  const [userName, setUserName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: userName, user_password: password }),
      });
      const data = (await res.json()) as {
        success: boolean;
        error_code: number;
        message: string;
      };
      if (!data.success) {
        setError(data.message);
        return;
      }
      const leaseError = await resumeOrAcquireAfterLogin(router);
      if (leaseError) {
        setError(leaseError);
        router.push("/lease");
      }
    } catch {
      setError("Login request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="mx-auto max-w-md">
      <CardHeader>
        <CardTitle>Login</CardTitle>
        <CardDescription>
          Email is your identity for leases and routing. An existing lease resumes on the same backend pod.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
