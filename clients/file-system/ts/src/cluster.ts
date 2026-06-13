import { err } from "neverthrow";

import { NativeFileEngine, type FileEngine } from "./io/engine.js";
import type { BytesResult, TextResult, UnitResult } from "./core/types.js";
import { TextEncoding, type TextEncoding as TextEncodingValue } from "./domain/enums.js";
import {
  validateBytesWrite,
  validatePath,
  validateTextWrite,
} from "./validation/paths.js";

export class Cluster {
  private readonly engine: FileEngine;

  public constructor(engine: FileEngine = new NativeFileEngine()) {
    this.engine = engine;
  }

  public readBytes(path: string): BytesResult {
    const validated = validatePath(path);
    if (validated.isErr()) {
      return err(validated.error);
    }
    return this.engine.readBytes(validated.value.path);
  }

  public writeBytes(path: string, data: Buffer): UnitResult {
    const validated = validateBytesWrite(path, data);
    if (validated.isErr()) {
      return err(validated.error);
    }
    return this.engine.writeBytes(validated.value.path, validated.value.data);
  }

  public readText(
    path: string,
    encoding: TextEncodingValue = TextEncoding.UTF8,
  ): TextResult {
    const validated = validatePath(path);
    if (validated.isErr()) {
      return err(validated.error);
    }
    return this.engine.readText(validated.value.path, encoding);
  }

  public writeText(
    path: string,
    text: string,
    encoding: TextEncodingValue = TextEncoding.UTF8,
  ): UnitResult {
    const validated = validateTextWrite(path, text, encoding);
    if (validated.isErr()) {
      return err(validated.error);
    }
    const request = validated.value;
    return this.engine.writeText(
      request.path,
      request.text,
      request.encoding,
    );
  }
}
