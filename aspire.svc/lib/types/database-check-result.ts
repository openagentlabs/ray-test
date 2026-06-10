/**
 * Application-wide database probe codes (string union — TypeScript-friendly).
 * Use these values across server actions, instrumentation, and logging attributes.
 */
export const DatabaseCheckResult = {
  Success: "success",
  NoFileExists: "no_file_exists",
  InvalidPath: "invalid_path",
  OpenFailed: "open_failed",
  CorruptOrUnreadable: "corrupt_or_unreadable",
} as const;

export type DatabaseCheckResultCode =
  (typeof DatabaseCheckResult)[keyof typeof DatabaseCheckResult];

export type ValidateEnvironmentResult =
  | { readonly ok: true }
  | {
      readonly ok: false;
      readonly message: string;
      readonly detail?: string;
    };

export type DatabaseCheckOutcome =
  | { readonly ok: true; readonly code: typeof DatabaseCheckResult.Success }
  | { readonly ok: false; readonly code: typeof DatabaseCheckResult.NoFileExists }
  | {
      readonly ok: false;
      readonly code:
        | typeof DatabaseCheckResult.InvalidPath
        | typeof DatabaseCheckResult.OpenFailed
        | typeof DatabaseCheckResult.CorruptOrUnreadable;
      readonly message: string;
      readonly detail?: string;
    };
