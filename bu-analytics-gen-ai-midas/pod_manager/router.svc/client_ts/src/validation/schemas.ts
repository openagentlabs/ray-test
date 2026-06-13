import { z } from "zod";

export const subSchema = z.string().trim().min(1).max(256);

export const assignmentEpochSchema = z.number().int().nonnegative();

export const configKeySchema = z.string().trim().min(1).max(256);

export const configValueSchema = z.string().max(65536);

export const configDescriptionSchema = z.string().max(1024);

export const acquireLeaseRequestSchema = z.object({ sub: subSchema });

export const releaseLeaseRequestSchema = z.object({ sub: subSchema });

export const heartbeatRequestSchema = z.object({
  sub: subSchema,
  assignmentEpoch: assignmentEpochSchema,
});

export const getServiceConfigRequestSchema = z.object({ configKey: configKeySchema });

export const putServiceConfigRequestSchema = z.object({
  configKey: configKeySchema,
  value: configValueSchema,
  description: configDescriptionSchema.optional().default(""),
});
