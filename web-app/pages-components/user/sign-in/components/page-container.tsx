"use client";

import { Eye, EyeOff, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DECISION_AI_NAME } from "@/pages-components/shared/decision-ai-brand";
import {
  AuthPageLayout,
  AuthPanel,
} from "@/pages-components/user/components/auth-page-layout";

export function SignInPageContainer() {
  const router = useRouter();
  const emailId = useId();
  const passwordId = useId();
  const rememberId = useId();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (!email.trim() || !password) {
        setError("Enter your email and password to continue.");
        return;
      }

      if (!email.includes("@")) {
        setError("Enter a valid email address.");
        return;
      }

      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { message?: string } | null;
        setError(body?.message ?? "We could not sign you in. Check your credentials.");
        return;
      }

      router.push("/pages/dashboard");
      router.refresh();
    } catch {
      setError("We could not sign you in. Check your connection and try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthPageLayout
      title="Sign in"
      description={`Access your ${DECISION_AI_NAME} workspace with your EXL credentials.`}
      aside={
        <>
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">
            Secure access
          </p>
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground lg:text-3xl">
            Analytics and decisioning, protected by design.
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground lg:text-base">
            Material-inspired hierarchy keeps focus on one primary action. Session
            handling, validation, and error feedback are built in for every screen size.
          </p>
        </>
      }
      footer={
        <>
          Don&apos;t have an account?{" "}
          <Link
            href="/pages/user/register"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Register
          </Link>
        </>
      }
    >
      <AuthPanel>
        <form
          className="flex flex-col gap-5"
          onSubmit={handleSubmit}
          noValidate
          aria-busy={isSubmitting}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor={emailId}>Email</Label>
            <Input
              id={emailId}
              name="email"
              type="email"
              inputMode="email"
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@company.com"
              aria-invalid={error !== null}
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor={passwordId}>Password</Label>
              <Link
                href="/pages/user/forgot-password"
                className="text-xs font-medium text-primary underline-offset-4 hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <Input
                id={passwordId}
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                aria-invalid={error !== null}
                disabled={isSubmitting}
                required
                className="pr-11"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="absolute top-1/2 right-1 -translate-y-1/2"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                disabled={isSubmitting}
              >
                {showPassword ? (
                  <EyeOff className="size-4" aria-hidden />
                ) : (
                  <Eye className="size-4" aria-hidden />
                )}
              </Button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id={rememberId}
              checked={rememberMe}
              onCheckedChange={(checked) => setRememberMe(checked === true)}
              disabled={isSubmitting}
            />
            <Label htmlFor={rememberId} className="font-normal text-muted-foreground">
              Remember me on this device
            </Label>
          </div>

          {error !== null ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <Button
            type="submit"
            disabled={isSubmitting}
            className="h-11 w-full text-base sm:h-10 sm:text-sm"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Signing in…
              </>
            ) : (
              "Sign in"
            )}
          </Button>
        </form>
      </AuthPanel>
    </AuthPageLayout>
  );
}
