"use client";

import { ArrowLeft, Loader2, MailCheck } from "lucide-react";
import Link from "next/link";
import { useId, useState, type FormEvent } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DECISION_AI_NAME } from "@/pages-components/shared/decision-ai-brand";
import {
  AuthPageLayout,
  AuthPanel,
} from "@/pages-components/user/components/auth-page-layout";

type ForgotPasswordPhase = "form" | "success";

export function ForgotPasswordPageContainer() {
  const emailId = useId();
  const [email, setEmail] = useState("");
  const [phase, setPhase] = useState<ForgotPasswordPhase>("form");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await new Promise((resolve) => setTimeout(resolve, 700));

      if (!email.trim()) {
        setError("Enter the email associated with your account.");
        return;
      }

      if (!email.includes("@")) {
        setError("Enter a valid email address.");
        return;
      }

      setPhase("success");
    } catch {
      setError("We could not send the reset link. Check your connection and try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthPageLayout
      title="Reset password"
      description={`We will email reset instructions if an account exists for ${DECISION_AI_NAME}.`}
      aside={
        <>
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">
            Account recovery
          </p>
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground lg:text-3xl">
            Clear guidance when access is lost.
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground lg:text-base">
            Avoid account enumeration in copy, confirm success without leaking whether an
            email is registered, and keep a single obvious path back to sign in.
          </p>
        </>
      }
      footer={
        <>
          Remember your password?{" "}
          <Link
            href="/pages/user/sign-in"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Back to sign in
          </Link>
        </>
      }
    >
      <AuthPanel>
        {phase === "success" ? (
          <div className="flex flex-col gap-5">
            <Alert variant="success">
              <MailCheck aria-hidden />
              <AlertTitle>Check your inbox</AlertTitle>
              <AlertDescription>
                If an account exists for <span className="font-medium">{email}</span>, you
                will receive password reset instructions shortly. Links expire after 30
                minutes.
              </AlertDescription>
            </Alert>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={() => {
                setPhase("form");
                setEmail("");
              }}
            >
              Send another link
            </Button>
          </div>
        ) : (
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
                  Sending link…
                </>
              ) : (
                "Send reset link"
              )}
            </Button>
          </form>
        )}

        <div className="mt-5 border-t border-border pt-4">
          <Link
            href="/pages/user/sign-in"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Back to sign in
          </Link>
        </div>
      </AuthPanel>
    </AuthPageLayout>
  );
}
