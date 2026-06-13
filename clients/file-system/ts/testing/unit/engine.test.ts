import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { ErrorCodes } from "../../src/core/errors.js";
import { TextEncoding } from "../../src/domain/enums.js";
import {
  LARGE_READ_THRESHOLD_BYTES,
  NativeFileEngine,
} from "../../src/io/engine.js";
import { assertErr, assertOk } from "../helpers.js";

describe("NativeFileEngine", () => {
  let tempDir: string;

  afterEach(() => {
    if (tempDir !== undefined) {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("reads empty files as empty buffers", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-engine-"));
    const target = join(tempDir, "empty.bin");
    writeFileSync(target, Buffer.alloc(0));

    const result = assertOk(new NativeFileEngine().readBytes(target));
    expect(result.length).toBe(0);
  });

  it("creates parent directories on write", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-engine-"));
    const target = join(tempDir, "nested", "dir", "file.bin");

    assertOk(new NativeFileEngine().writeBytes(target, Buffer.from("payload")));
    expect(assertOk(new NativeFileEngine().readBytes(target)).toString()).toBe(
      "payload",
    );
  });

  it("returns not_found for missing files", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-engine-"));
    assertErr(
      new NativeFileEngine().readBytes(join(tempDir, "missing.bin")),
      ErrorCodes.NOT_FOUND,
    );
  });

  it("returns validation when reading a directory", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-engine-"));
    assertErr(new NativeFileEngine().readBytes(tempDir), ErrorCodes.VALIDATION);
  });

  it("returns encoding errors for invalid ASCII payloads", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-engine-"));
    const target = join(tempDir, "bytes.bin");
    writeFileSync(target, Buffer.from([0xff, 0xfe]));

    assertErr(
      new NativeFileEngine().readText(target, TextEncoding.ASCII),
      ErrorCodes.ENCODING,
    );
  });

  it("reads files larger than the buffered threshold", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-engine-"));
    const target = join(tempDir, "large.bin");
    const payload = Buffer.alloc(LARGE_READ_THRESHOLD_BYTES + 1, 0x78);
    writeFileSync(target, payload);

    const result = assertOk(new NativeFileEngine().readBytes(target));
    expect(result.equals(payload)).toBe(true);
  });
});
