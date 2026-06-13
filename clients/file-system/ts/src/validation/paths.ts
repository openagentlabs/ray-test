import { err, ok } from "neverthrow";

import { formatValidationDetail } from "../core/error-format.js";
import { ErrorCodes, appError } from "../core/errors.js";
import type { FsResult } from "../core/types.js";
import type { TextEncoding } from "../domain/enums.js";
import {
  BytesWriteRequestSchema,
  PathRequestSchema,
  TextWriteRequestSchema,
  type BytesWriteRequest,
  type PathRequest,
  type TextWriteRequest,
} from "../domain/schemas.js";

export function validatePath(path: string): FsResult<PathRequest> {
  const parsed = PathRequestSchema.safeParse({ path });
  if (!parsed.success) {
    return err(
      appError(
        ErrorCodes.VALIDATION,
        "Invalid path.",
        formatValidationDetail(parsed.error),
      ),
    );
  }
  return ok(parsed.data);
}

export function validateTextWrite(
  path: string,
  text: string,
  encoding: TextEncoding,
): FsResult<TextWriteRequest> {
  const parsed = TextWriteRequestSchema.safeParse({ path, text, encoding });
  if (!parsed.success) {
    return err(
      appError(
        ErrorCodes.VALIDATION,
        "Invalid text write request.",
        formatValidationDetail(parsed.error),
      ),
    );
  }
  return ok(parsed.data);
}

export function validateBytesWrite(
  path: string,
  data: Buffer,
): FsResult<BytesWriteRequest> {
  const parsed = BytesWriteRequestSchema.safeParse({ path, data });
  if (!parsed.success) {
    return err(
      appError(
        ErrorCodes.VALIDATION,
        "Invalid binary write request.",
        formatValidationDetail(parsed.error),
      ),
    );
  }
  return ok(parsed.data);
}
