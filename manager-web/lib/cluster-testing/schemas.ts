import { z } from "zod";

export const sharedMountKindSchema = z.enum(["lustre", "s3-shared-files"]);

export const runSharedMountTestRequestSchema = z.object({
  mountKind: sharedMountKindSchema,
});

export type RunSharedMountTestRequest = z.infer<
  typeof runSharedMountTestRequestSchema
>;
