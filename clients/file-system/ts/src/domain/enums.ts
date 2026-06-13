export const TextEncoding = {
  UTF8: "utf-8",
  UTF16: "utf-16",
  ASCII: "ascii",
  LATIN1: "latin1",
} as const;

export type TextEncoding = (typeof TextEncoding)[keyof typeof TextEncoding];
