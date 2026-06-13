import { describe, expect, it } from "vitest";

import { ErrorCodes } from "../../src/core/errors.js";
import { TextEncoding } from "../../src/domain/enums.js";
import {
  validateBytesWrite,
  validatePath,
  validateTextWrite,
} from "../../src/validation/paths.js";
import { assertErr, assertOk } from "../helpers.js";

describe("validatePath", () => {
  it("accepts non-empty paths", () => {
    const result = assertOk(validatePath("config/app.json"));
    expect(result.path).toBe("config/app.json");
  });

  it("rejects empty paths", () => {
    assertErr(validatePath(""), ErrorCodes.VALIDATION);
  });
});

describe("validateTextWrite", () => {
  it("defaults encoding through schema input", () => {
    const result = assertOk(
      validateTextWrite("out.txt", "payload", TextEncoding.UTF8),
    );
    expect(result.text).toBe("payload");
    expect(result.encoding).toBe(TextEncoding.UTF8);
  });
});

describe("validateBytesWrite", () => {
  it("accepts empty payloads", () => {
    const result = assertOk(validateBytesWrite("empty.bin", Buffer.alloc(0)));
    expect(result.data.length).toBe(0);
  });
});
