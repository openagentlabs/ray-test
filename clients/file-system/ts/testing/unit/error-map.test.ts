import { describe, expect, it } from "vitest";

import { ErrorCodes } from "../../src/core/errors.js";
import { ioError, mapNodeError } from "../../src/core/error-map.js";

describe("mapNodeError", () => {
  it("maps ENOENT to not_found", () => {
    const error = mapNodeError(
      Object.assign(new Error("missing"), { code: "ENOENT" }),
      "read",
      "/tmp/missing.bin",
    );
    expect(error.code).toBe(ErrorCodes.NOT_FOUND);
  });

  it("maps EACCES to permission", () => {
    const error = mapNodeError(
      Object.assign(new Error("denied"), { code: "EACCES" }),
      "read",
      "/tmp/locked.bin",
    );
    expect(error.code).toBe(ErrorCodes.PERMISSION);
  });

  it("maps EISDIR to validation", () => {
    const error = mapNodeError(
      Object.assign(new Error("is dir"), { code: "EISDIR" }),
      "read",
      "/tmp/dir",
    );
    expect(error.code).toBe(ErrorCodes.VALIDATION);
  });

  it("maps ENOSPC to io", () => {
    const error = mapNodeError(
      Object.assign(new Error("full"), { code: "ENOSPC" }),
      "write",
      "/tmp/full.bin",
    );
    expect(error.code).toBe(ErrorCodes.IO);
  });

  it("rethrows unexpected errno codes", () => {
    expect(() =>
      mapNodeError(
        Object.assign(new Error("unexpected"), { code: "UNKNOWN" }),
        "read",
        "/tmp/other.bin",
      ),
    ).toThrow("unexpected");
  });

  it("builds ioError helper messages", () => {
    const error = ioError("write", "/tmp/target.bin", "disk full");
    expect(error.code).toBe(ErrorCodes.IO);
    expect(error.message).toContain("write");
  });
});
