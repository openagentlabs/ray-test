import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { Cluster, ErrorCodes, TextEncoding } from "../../src/index.js";
import { assertErr, assertOk } from "../helpers.js";

describe("Cluster integration", () => {
  let tempDir: string;

  afterEach(() => {
    if (tempDir !== undefined) {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("round-trips text files", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-cluster-"));
    const cluster = new Cluster();
    const target = join(tempDir, "hello.txt");

    assertOk(cluster.writeText(target, "hello world"));
    assertOk(cluster.readText(target));
    expect(assertOk(cluster.readText(target))).toBe("hello world");
  });

  it("round-trips binary files", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-cluster-"));
    const cluster = new Cluster();
    const target = join(tempDir, "payload.bin");
    const payload = Buffer.from([0x00, 0x01, 0x62, 0x69, 0x6e, 0x61, 0x72, 0x79]);

    assertOk(cluster.writeBytes(target, payload));
    expect(assertOk(cluster.readBytes(target)).equals(payload)).toBe(true);
  });

  it("returns not_found for missing files", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-cluster-"));
    const cluster = new Cluster();
    const error = assertErr(
      cluster.readBytes(join(tempDir, "missing.bin")),
      ErrorCodes.NOT_FOUND,
    );
    expect(error.message.toLowerCase()).toContain("not found");
  });

  it("returns validation when reading a directory", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-cluster-"));
    assertErr(new Cluster().readBytes(tempDir), ErrorCodes.VALIDATION);
  });

  it("returns encoding errors for invalid ASCII reads", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-cluster-"));
    const target = join(tempDir, "bytes.bin");
    writeFileSync(target, Buffer.from([0xff, 0xfe]));

    assertErr(
      new Cluster().readText(target, TextEncoding.ASCII),
      ErrorCodes.ENCODING,
    );
  });

  it("supports non-utf8 encodings", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-cluster-"));
    const cluster = new Cluster();
    const target = join(tempDir, "latin.txt");
    const text = "café";

    assertOk(cluster.writeText(target, text, TextEncoding.LATIN1));
    expect(assertOk(cluster.readText(target, TextEncoding.LATIN1))).toBe(text);
  });

  it("overwrites existing files atomically", () => {
    tempDir = mkdtempSync(join(tmpdir(), "fs-cluster-"));
    const cluster = new Cluster();
    const target = join(tempDir, "state.txt");

    assertOk(cluster.writeText(target, "version-1"));
    assertOk(cluster.writeText(target, "version-2"));
    expect(assertOk(cluster.readText(target))).toBe("version-2");
  });
});
