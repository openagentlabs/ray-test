"use client";

import { Eye, EyeOff, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DECISION_AI_NAME } from "@/pages-components/shared/decision-ai-brand";
import {
  AuthPageLayout,
  AuthPanel,
} from "@/pages-components/user/components/auth-page-layout";

export function RegisterPageContainer() {
  const router = useRouter();
  const displayNameId = useId();
  const emailId = useId();
  const passwordId = useId();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await new Promise((resolve) => setTimeout(resolve, 600));

      if (!displayName.trim() || !email.trim() || !password) {
        setError("Enter your name, email, and password to continue.");
        return;
      }

      if (!email.includes("@")) {
        setError("Enter a valid email address.");
        return;
      }

      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }

      router.push("/pages/dashboard");
    } catch {
      setError("We could not create your account. Check your connection and try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthPageLayout
      title="Create account"
      description={`Register for ${DECISION_AI_NAME} with your work email.`}
      aside={
        <>
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">
            Get started
          </p>
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground lg:text-3xl">
            Join your team on a secure analytics workspace.
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground lg:text-base">
            One primary action per screen, accessible forms, and clear validation
            feedback on every device size.
          </p>
        </>
      }
      footer={
        <>
          Already have an account?{" "}
          <Link
            href="/pages/user/sign-in"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Sign in
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
            <Label htmlFor={displayNameId}>Display name</Label>
            <Input
              id={displayNameId}
              name="displayName"
              type="text"
              autoComplete="name"
              autoFocus
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Your name"
              aria-invalid={error !== null}
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor={emailId}>Email</Label>
            <Input
              id={emailId}
              name="email"
              type="email"
              inputMode="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@company.com"
              aria-invalid={error !== null}
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor={passwordId}>Password</Label>
            <div className="relative">
              <Input
                id={passwordId}
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="At least 8 characters"
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
                Creating account…
              </>
            ) : (
              "Create account"
            )}
          </Button>
        </form>
      </AuthPanel>
    </AuthPageLayout>
  );
}
