import { ok } from "neverthrow";
import { describe, expect, it } from "vitest";

import { Cluster } from "../../src/cluster.js";
import type { BytesResult, TextResult, UnitResult } from "../../src/core/types.js";
import { TextEncoding } from "../../src/domain/enums.js";
import { FileEngine } from "../../src/io/engine.js";
import { assertOk } from "../helpers.js";

class RecordingEngine extends FileEngine {
  public readonly readBytesPaths: string[] = [];
  public readonly writeBytesCalls: Array<{ path: string; data: Buffer }> = [];
  public readonly readTextCalls: Array<{ path: string; encoding: TextEncoding }> =
    [];
  public readonly writeTextCalls: Array<{
    path: string;
    text: string;
    encoding: TextEncoding;
  }> = [];

  readBytes(path: string): BytesResult {
    this.readBytesPaths.push(path);
    return ok(Buffer.from("stub-bytes"));
  }

  writeBytes(path: string, data: Buffer): UnitResult {
    this.writeBytesCalls.push({ path, data });
    return ok(undefined);
  }

  readText(path: string, encoding: TextEncoding): TextResult {
    this.readTextCalls.push({ path, encoding });
    return ok("stub-text");
  }

  writeText(path: string, text: string, encoding: TextEncoding): UnitResult {
    this.writeTextCalls.push({ path, text, encoding });
    return ok(undefined);
  }
}

describe("Cluster delegation", () => {
  it("delegates readBytes to the injected engine", () => {
    const engine = new RecordingEngine();
    const cluster = new Cluster(engine);

    const result = assertOk(cluster.readBytes("data/file.bin"));
    expect(result.toString()).toBe("stub-bytes");
    expect(engine.readBytesPaths).toEqual(["data/file.bin"]);
  });

  it("delegates writeBytes to the injected engine", () => {
    const engine = new RecordingEngine();
    const cluster = new Cluster(engine);
    const payload = Buffer.from([0x01]);

    assertOk(cluster.writeBytes("out.bin", payload));
    expect(engine.writeBytesCalls).toEqual([{ path: "out.bin", data: payload }]);
  });

  it("delegates text operations to the injected engine", () => {
    const engine = new RecordingEngine();
    const cluster = new Cluster(engine);

    assertOk(cluster.readText("in.txt", TextEncoding.LATIN1));
    assertOk(cluster.writeText("out.txt", "hi", TextEncoding.UTF16));

    expect(engine.readTextCalls).toEqual([
      { path: "in.txt", encoding: TextEncoding.LATIN1 },
    ]);
    expect(engine.writeTextCalls).toEqual([
      { path: "out.txt", text: "hi", encoding: TextEncoding.UTF16 },
    ]);
  });
});
