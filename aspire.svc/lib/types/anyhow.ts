/**
 * TypeScript equivalents for Rust `anyhow`-style error handling.
 * Use {@link AnyhowResult} for fallible returns; avoid throwing across boundaries.
 */

export interface AnyhowContextFrame {
  readonly label: string;
  readonly detail?: string;
}

export interface AnyhowError {
  readonly message: string;
  readonly context: readonly AnyhowContextFrame[];
}

export type AnyhowResult<T> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly error: AnyhowError };

export class AnyhowResultFactory {
  public static ok<T>(value: T): AnyhowResult<T> {
    return { ok: true, value };
  }

  public static err(
    message: string,
    context: readonly AnyhowContextFrame[] = [],
  ): AnyhowResult<never> {
    return {
      ok: false,
      error: { message, context },
    };
  }

  public static formatError(error: AnyhowError): string {
    if (error.context.length === 0) {
      return error.message;
    }

    const chain = error.context
      .map((frame) =>
        frame.detail !== undefined ? `${frame.label}: ${frame.detail}` : frame.label,
      )
      .join(" → ");

    return `${error.message} (${chain})`;
  }

  private constructor() {}
}

export type SignOutResult = AnyhowResult<void>;

export type SessionLoadResult = AnyhowResult<{
  readonly userId: string;
  readonly displayName: string;
  readonly email: string;
}>;
