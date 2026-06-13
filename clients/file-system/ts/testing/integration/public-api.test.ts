import { describe, expect, it } from "vitest";

import { AppError, Cluster, ErrorCodes, TextEncoding } from "../../src/index.js";

describe("public exports", () => {
  it("exposes the expected Cluster API surface", () => {
    expect(Cluster).toBeTypeOf("function");
    expect(ErrorCodes.NOT_FOUND).toBe("not_found");
    expect(TextEncoding.UTF8).toBe("utf-8");
  });

  it("constructs a default Cluster", () => {
    expect(new Cluster()).toBeInstanceOf(Cluster);
  });

  it("keeps AppError objects readonly at the type level", () => {
    const error: AppError = {
      code: ErrorCodes.IO,
      message: "failed",
      detail: "disk",
    };
    expect(error.code).toBe(ErrorCodes.IO);
  });
});
