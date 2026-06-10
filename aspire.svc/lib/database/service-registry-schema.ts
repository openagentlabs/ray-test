/** SQL DDL + seed rows for `service-registry.sqlite` (aligned with `scripts/booter.mjs`). */

export const SERVICE_REGISTRY_SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS registered_services (
  id TEXT PRIMARY KEY NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('application', 'service')),
  kind TEXT NOT NULL CHECK (kind IN ('node', 'shell', 'python')),
  workdir_relative TEXT NOT NULL,
  command TEXT NOT NULL,
  args_json TEXT NOT NULL DEFAULT '[]',
  port INTEGER,
  health_kind TEXT NOT NULL DEFAULT 'none' CHECK (health_kind IN ('none', 'http', 'tcp')),
  health_target TEXT,
  description TEXT,
  start_order INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  auto_start_with_home INTEGER NOT NULL DEFAULT 0,
  env_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_registered_services_order
  ON registered_services (enabled, start_order);
`;

export interface ServiceRegistrySeedRow {
  readonly id: string;
  readonly display_name: string;
  readonly role: "application" | "service";
  readonly kind: "node" | "shell" | "python";
  readonly workdir_relative: string;
  readonly command: string;
  readonly args_json: string;
  readonly port: number | null;
  readonly health_kind: "none" | "http" | "tcp";
  readonly health_target: string | null;
  readonly description: string;
  readonly start_order: number;
  readonly enabled: 0 | 1;
  /** 1 = auto-spawn once when Aspire home is first shown this browser session (typically `arb-frontend`). */
  readonly auto_start_with_home: 0 | 1;
  readonly env_json: string | null;
}

/** Canonical local ports: aspire 8801, frontend 8802, IAM gRPC 8803, solutions 8804, storage 8805, general AI agent 8806. */
export const SERVICE_REGISTRY_DEFAULT_SEED: readonly ServiceRegistrySeedRow[] =
  Object.freeze([
    {
      id: "iam-service",
      display_name: "IAM (gRPC)",
      role: "service",
      kind: "shell",
      workdir_relative: "iam.svc/server",
      command: ".venv/bin/iam-service",
      args_json: "[]",
      port: 8803,
      health_kind: "tcp",
      health_target: "127.0.0.1",
      description:
        "Identity and access microservice (gRPC; run from iam.svc/server with venv installed).",
      start_order: 10,
      enabled: 1,
      auto_start_with_home: 0,
      env_json: null,
    },
    {
      id: "general-ai-agent",
      display_name: "General AI agent (gRPC)",
      role: "service",
      kind: "shell",
      workdir_relative: "general.ai.agent.svc/server",
      command: ".venv/bin/general-ai-agent-service",
      args_json: "[]",
      port: 8806,
      health_kind: "tcp",
      health_target: "127.0.0.1",
      description:
        "Strands + Bedrock agent over gRPC (run from general.ai.agent.svc/server; AWS + app_config.toml).",
      start_order: 15,
      enabled: 1,
      auto_start_with_home: 0,
      env_json: null,
    },
    {
      id: "solutions-grpc",
      display_name: "Solutions (gRPC)",
      role: "service",
      kind: "python",
      workdir_relative: "solutions.svc/server",
      command: "python3",
      args_json: JSON.stringify(["-m", "solutions_service"]),
      port: 8804,
      health_kind: "tcp",
      health_target: "127.0.0.1",
      description:
        "ARB solutions gRPC server (listen port in app_config.toml; requires pip install -e . in server/).",
      start_order: 20,
      enabled: 1,
      auto_start_with_home: 0,
      env_json: JSON.stringify({ SOLUTIONS_APP_CONFIG_PATH: "./app_config.toml" }),
    },
    {
      id: "storage-grpc",
      display_name: "Storage (gRPC)",
      role: "service",
      kind: "shell",
      workdir_relative: "storage.svc/server",
      command: ".venv/bin/arb-storage-service",
      args_json: "[]",
      port: 8805,
      health_kind: "tcp",
      health_target: "127.0.0.1",
      description:
        "Storage microservice (gRPC; run from storage.svc/server with venv installed).",
      start_order: 22,
      enabled: 1,
      auto_start_with_home: 0,
      env_json: null,
    },
    {
      id: "arb-frontend",
      display_name: "Arb Frontend (Next.js)",
      role: "application",
      kind: "node",
      workdir_relative: "frontend",
      command: "npm",
      args_json: JSON.stringify(["run", "dev"]),
      port: 8802,
      health_kind: "http",
      health_target: "http://127.0.0.1:8802/",
      description: "Primary Next.js workspace under frontend/ (npm run dev on port 8802).",
      start_order: 25,
      enabled: 1,
      auto_start_with_home: 1,
      env_json: null,
    },
    {
      id: "aspire-frontend",
      display_name: "Arb Aspire (Next.js)",
      role: "application",
      kind: "node",
      workdir_relative: "aspire.svc",
      command: "npm",
      args_json: JSON.stringify(["run", "dev"]),
      port: 8801,
      health_kind: "http",
      health_target: "http://127.0.0.1:8801/",
      description: "Aspire architect host Next.js app (npm run dev on port 8801).",
      start_order: 30,
      enabled: 1,
      auto_start_with_home: 0,
      env_json: null,
    },
  ]);
