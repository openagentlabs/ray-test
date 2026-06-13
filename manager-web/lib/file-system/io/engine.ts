import {
  closeSync,
  mkdirSync,
  openSync,
  readFileSync,
  readSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname } from "node:path";
import { err, ok } from "neverthrow";

import { mapNodeError } from "../core/error-map";
import { ErrorCodes, appError } from "../core/errors";
import type { BytesResult, TextResult, UnitResult } from "../core/types";
import type { TextEncoding } from "../domain/enums";
import { TextEncoding as TextEncodingValues } from "../domain/enums";
import { toBufferEncoding, toTextDecoderLabel } from "../domain/encoding";

import { withMountRetrySync } from "@/lib/mount/mount-retry";
import { isTransientMountErrno } from "@/lib/mount/shared-mount-health";

export const LARGE_READ_THRESHOLD_BYTES = 16 * 1024 * 1024;

export abstract class FileEngine {
  abstract readBytes(path: string): BytesResult;

  abstract writeBytes(path: string, data: Buffer): UnitResult;

  abstract readText(path: string, encoding: TextEncoding): TextResult;

  abstract writeText(
    path: string,
    text: string,
    encoding: TextEncoding,
  ): UnitResult;
}

export class NativeFileEngine extends FileEngine {
  readBytes(path: string): BytesResult {
    try {
      return withMountRetrySync(() => this.readBytesOnce(path));
    } catch (error) {
      if (!isErrnoException(error)) {
        throw error;
      }
      return err(mapNodeError(error, "read", path));
    }
  }

  private readBytesOnce(path: string): BytesResult {
    try {
      const stat = statSync(path);
      if (stat.isDirectory()) {
        return err(
          appError(
            ErrorCodes.VALIDATION,
            `Expected a file but found a directory: '${path}'.`,
          ),
        );
      }
      if (stat.size === 0) {
        return ok(Buffer.alloc(0));
      }
      if (stat.size <= LARGE_READ_THRESHOLD_BYTES) {
        return ok(readFileSync(path));
      }
      return ok(readLargeFile(path, stat.size));
    } catch (error) {
      if (!isErrnoException(error)) {
        throw error;
      }
      if (isTransientMountErrno(error.code)) {
        throw error;
      }
      return err(mapNodeError(error, "read", path));
    }
  }

  writeBytes(path: string, data: Buffer): UnitResult {
    try {
      return withMountRetrySync(() => this.writeBytesOnce(path, data));
    } catch (error) {
      if (!isErrnoException(error)) {
        throw error;
      }
      return err(mapNodeError(error, "write", path));
    }
  }

  private writeBytesOnce(path: string, data: Buffer): UnitResult {
    try {
      mkdirSync(dirname(path), { recursive: true });
    } catch (error) {
      if (!isErrnoException(error)) {
        throw error;
      }
      if (isTransientMountErrno(error.code)) {
        throw error;
      }
      return err(mapNodeError(error, "prepare", path));
    }

    const tempPath = `${dirname(path)}/.${basename(path)}.${process.pid}.tmp`;

    try {
      writeFileSync(tempPath, data);
      renameSync(tempPath, path);
      return ok(undefined);
    } catch (error) {
      try {
        unlinkSync(tempPath);
      } catch {
        // Best-effort cleanup of temp file.
      }
      if (!isErrnoException(error)) {
        throw error;
      }
      if (isTransientMountErrno(error.code)) {
        throw error;
      }
      return err(mapNodeError(error, "write", path));
    }
  }

  readText(path: string, encoding: TextEncoding): TextResult {
    const raw = this.readBytes(path);
    if (raw.isErr()) {
      return err(raw.error);
    }
    return decodeText(raw.value, encoding, path);
  }

  writeText(path: string, text: string, encoding: TextEncoding): UnitResult {
    let data: Buffer;
    try {
      data = Buffer.from(text, toBufferEncoding(encoding));
    } catch (error) {
      if (!(error instanceof Error)) {
        throw error;
      }
      return err(
        appError(
          ErrorCodes.ENCODING,
          `Could not encode text for '${path}' as ${encoding}.`,
          error.message,
        ),
      );
    }
    return this.writeBytes(path, data);
  }
}

function decodeText(
  buffer: Buffer,
  encoding: TextEncoding,
  path: string,
): TextResult {
  if (
    encoding === TextEncodingValues.ASCII &&
    buffer.some((byte) => byte > 0x7f)
  ) {
    return err(
      appError(
        ErrorCodes.ENCODING,
        `Could not decode '${path}' as ${encoding}.`,
        "Invalid ASCII byte sequence.",
      ),
    );
  }

  try {
    const decoder = new TextDecoder(toTextDecoderLabel(encoding), {
      fatal: true,
    });
    return ok(decoder.decode(buffer));
  } catch (error) {
    if (!(error instanceof Error)) {
      throw error;
    }
    return err(
      appError(
        ErrorCodes.ENCODING,
        `Could not decode '${path}' as ${encoding}.`,
        error.message,
      ),
    );
  }
}

function readLargeFile(path: string, size: number): Buffer {
  const fd = openSync(path, "r");
  try {
    const buffer = Buffer.alloc(size);
    let offset = 0;
    while (offset < size) {
      const bytesRead = readSync(fd, buffer, offset, size - offset, offset);
      if (bytesRead === 0) {
        break;
      }
      offset += bytesRead;
    }
    return buffer;
  } finally {
    closeSync(fd);
  }
}

function isErrnoException(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && "code" in error;
}
