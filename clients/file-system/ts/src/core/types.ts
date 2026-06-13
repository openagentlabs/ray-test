import type { Result } from "neverthrow";

import type { AppError } from "./errors.js";

export type FsResult<T> = Result<T, AppError>;
export type TextResult = FsResult<string>;
export type BytesResult = FsResult<Buffer>;
export type UnitResult = FsResult<void>;
