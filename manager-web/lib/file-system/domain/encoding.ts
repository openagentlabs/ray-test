import type { TextEncoding } from "../domain/enums";
import { TextEncoding as TextEncodingValues } from "../domain/enums";

export function toBufferEncoding(encoding: TextEncoding): BufferEncoding {
  switch (encoding) {
    case TextEncodingValues.UTF8:
      return "utf-8";
    case TextEncodingValues.UTF16:
      return "utf16le";
    case TextEncodingValues.ASCII:
      return "ascii";
    case TextEncodingValues.LATIN1:
      return "latin1";
  }
}

export function toTextDecoderLabel(encoding: TextEncoding): string {
  switch (encoding) {
    case TextEncodingValues.UTF16:
      return "utf-16le";
    default:
      return encoding;
  }
}
