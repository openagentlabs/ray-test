/** Immutable error carried in {@link Result} err branches. */
export interface AppError {
  readonly code: string;
  readonly message: string;
  readonly detail?: string;
}

export const ErrorCodes = {
  VALIDATION: "validation",
  NOT_FOUND: "not_found",
  PERMISSION: "permission",
  IO: "io",
  ENCODING: "encoding",
} as const;

export type ErrorCode = (typeof ErrorCodes)[keyof typeof ErrorCodes];

export function appError(
  code: ErrorCode,
  message: string,
  detail?: string,
): AppError {
  return detail === undefined ? { code, message } : { code, message, detail };
}
