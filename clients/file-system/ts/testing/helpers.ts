import { expect } from "vitest";
import type { Result } from "neverthrow";

import type { AppError } from "../src/core/errors.js";

export function assertOk<T>(result: Result<T, AppError>): T {
  expect(result.isOk()).toBe(true);
  if (result.isErr()) {
    throw new Error("expected Ok result");
  }
  return result.value;
}

export function assertErr(
  result: Result<unknown, AppError>,
  code?: string,
): AppError {
  expect(result.isErr()).toBe(true);
  if (result.isOk()) {
    throw new Error("expected Err result");
  }
  if (code !== undefined) {
    expect(result.error.code).toBe(code);
  }
  return result.error;
}
