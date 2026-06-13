import { z } from "zod";

import { TextEncoding } from "./enums.js";

export const PathRequestSchema = z.object({
  path: z.string().min(1),
});

export type PathRequest = z.infer<typeof PathRequestSchema>;

export const TextWriteRequestSchema = z.object({
  path: z.string().min(1),
  text: z.string(),
  encoding: z.enum([
    TextEncoding.UTF8,
    TextEncoding.UTF16,
    TextEncoding.ASCII,
    TextEncoding.LATIN1,
  ]),
});

export type TextWriteRequest = z.infer<typeof TextWriteRequestSchema>;

export const BytesWriteRequestSchema = z.object({
  path: z.string().min(1),
  data: z.instanceof(Buffer),
});

export type BytesWriteRequest = z.infer<typeof BytesWriteRequestSchema>;
