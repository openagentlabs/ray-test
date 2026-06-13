import { z } from "zod";

export class PodManagerClientValidationError extends Error {
  readonly rpcName: string;
  readonly fieldErrors: Readonly<Record<string, string>>;

  constructor(message: string, rpcName: string, fieldErrors: Readonly<Record<string, string>>) {
    super(message);
    this.name = "PodManagerClientValidationError";
    this.rpcName = rpcName;
    this.fieldErrors = fieldErrors;
  }
}

function fieldErrorsFromZod(err: z.ZodError): Record<string, string> {
  const flat = err.flatten().fieldErrors as Record<string, string[] | undefined>;
  const out: Record<string, string> = {};
  for (const [key, messages] of Object.entries(flat)) {
    const first = messages?.[0];
    if (first) out[key] = first;
  }
  return out;
}

export function assertValidRequest<T>(schema: z.ZodType<T>, request: unknown, rpcName: string): T {
  const parsed = schema.safeParse(request);
  if (!parsed.success) {
    const fieldErrors = fieldErrorsFromZod(parsed.error);
    const message =
      parsed.error.issues
        .map((issue) => {
          const field = issue.path.map(String).join(".");
          return field ? `${field}: ${issue.message}` : issue.message;
        })
        .slice(0, 4)
        .join("; ") || "Request validation failed.";
    throw new PodManagerClientValidationError(message, rpcName, fieldErrors);
  }
  return parsed.data;
}
