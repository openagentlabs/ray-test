import { z } from "zod";

const DeployTargetSchema = z.enum(["local", "aws"]);

const UrlSchema = z
  .string()
  .url()
  .transform((value) => value.replace(/\/$/, ""));

export type DeployTarget = z.infer<typeof DeployTargetSchema>;

export function deployTarget(): DeployTarget {
  const raw = process.env.POD_MANAGER_DEPLOY_TARGET ?? "local";
  const parsed = DeployTargetSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error(
      `Invalid POD_MANAGER_DEPLOY_TARGET=${raw!}; expected local or aws`,
    );
  }
  return parsed.data;
}

export function envoyUrl(): string {
  const defaultUrl =
    deployTarget() === "aws"
      ? process.env.NEXT_PUBLIC_ENVOY_URL
      : (process.env.NEXT_PUBLIC_ENVOY_URL ?? "http://localhost:10000");
  if (!defaultUrl) {
    throw new Error(
      "NEXT_PUBLIC_ENVOY_URL is required when POD_MANAGER_DEPLOY_TARGET=aws",
    );
  }
  return UrlSchema.parse(defaultUrl);
}

export function podManagerGrpcHost(): string {
  if (process.env.POD_MANAGER_GRPC_HOST) {
    return process.env.POD_MANAGER_GRPC_HOST;
  }
  return deployTarget() === "aws" ? "" : "localhost";
}

export function podManagerGrpcPort(): number {
  const port = Number(process.env.POD_MANAGER_GRPC_PORT ?? "8804");
  if (!Number.isFinite(port) || port <= 0) {
    throw new Error(`Invalid POD_MANAGER_GRPC_PORT=${process.env.POD_MANAGER_GRPC_PORT}`);
  }
  return port;
}

export function assertGrpcConfigured(): void {
  if (deployTarget() === "aws" && !podManagerGrpcHost()) {
    throw new Error(
      "POD_MANAGER_GRPC_HOST is required when POD_MANAGER_DEPLOY_TARGET=aws",
    );
  }
}

export const SESSION_COOKIE = "pod_manager_user";
