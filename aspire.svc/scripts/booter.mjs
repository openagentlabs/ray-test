#!/usr/bin/env node
/**
 * Arb Aspire service booter: reads `service-registry.sqlite` in the aspire.svc folder,
 * registers runnable applications and backend services, and supports list / search /
 * status / start / stop against that catalog.
 *
 * Run from the aspire.svc directory (e.g. `npm run boot:list`).
 */

import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import Database from "better-sqlite3";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ASPIRE_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(ASPIRE_ROOT, "..");
const REGISTRY_DB = path.join(ASPIRE_ROOT, "service-registry.sqlite");
const STATE_PATH = path.join(ASPIRE_ROOT, ".aspire", "booter-pids.json");

const SCHEMA = `
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

const DEFAULT_ROWS = [
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
];

function ensureAutoStartWithHomeColumn(db) {
  const cols = db.prepare("PRAGMA table_info(registered_services)").all();
  const names = new Set(cols.map((c) => c.name));
  if (!names.has("auto_start_with_home")) {
    db.exec(
      "ALTER TABLE registered_services ADD COLUMN auto_start_with_home INTEGER NOT NULL DEFAULT 0",
    );
  }
}

function openDb() {
  fs.mkdirSync(path.dirname(STATE_PATH), { recursive: true });
  const db = new Database(REGISTRY_DB);
  db.exec(SCHEMA);
  ensureAutoStartWithHomeColumn(db);
  return db;
}

function readState() {
  try {
    const raw = fs.readFileSync(STATE_PATH, "utf8");
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function writeState(state) {
  fs.mkdirSync(path.dirname(STATE_PATH), { recursive: true });
  fs.writeFileSync(STATE_PATH, JSON.stringify(state, null, 2), "utf8");
}

function isAlive(pid) {
  if (typeof pid !== "number" || pid <= 0) {
    return false;
  }
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function tcpOpen(host, port, timeoutMs = 800) {
  return new Promise((resolve) => {
    const socket = net.connect({ host, port }, () => {
      socket.destroy();
      resolve(true);
    });
    socket.setTimeout(timeoutMs);
    socket.on("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.on("error", () => resolve(false));
  });
}

function httpOk(url, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const req = http.get(
      url,
      { timeout: timeoutMs },
      (res) => {
        res.resume();
        resolve(res.statusCode !== undefined && res.statusCode < 500);
      },
    );
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function probeHealth(row) {
  if (row.health_kind === "http" && row.health_target) {
    return httpOk(row.health_target);
  }
  if (row.health_kind === "tcp" && row.port != null && row.health_target) {
    return tcpOpen(row.health_target, row.port);
  }
  if (row.port != null) {
    return tcpOpen("127.0.0.1", row.port);
  }
  return false;
}

function resolveWorkdir(rel) {
  return path.join(REPO_ROOT, rel);
}

function npmCommand() {
  return process.platform === "win32" ? "npm.cmd" : "npm";
}

function normalizeCommand(row) {
  if (row.command === "npm") {
    return npmCommand();
  }
  return row.command;
}

function parseArgs(row) {
  try {
    const parsed = JSON.parse(row.args_json);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function parseEnv(row) {
  if (!row.env_json) {
    return {};
  }
  try {
    const parsed = JSON.parse(row.env_json);
    return typeof parsed === "object" && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

function cmdInit() {
  const db = openDb();
  const insert = db.prepare(`
    INSERT OR REPLACE INTO registered_services (
      id, display_name, role, kind, workdir_relative, command, args_json,
      port, health_kind, health_target, description, start_order, enabled,
      auto_start_with_home, env_json
    ) VALUES (
      @id, @display_name, @role, @kind, @workdir_relative, @command, @args_json,
      @port, @health_kind, @health_target, @description, @start_order, @enabled,
      @auto_start_with_home, @env_json
    )
  `);
  const tx = db.transaction(() => {
    for (const row of DEFAULT_ROWS) {
      insert.run(row);
    }
  });
  tx();
  db.close();
  console.log(`Initialized registry at ${REGISTRY_DB}`);
}

function cmdList(db) {
  const rows = db
    .prepare(
      `SELECT * FROM registered_services WHERE enabled = 1 ORDER BY start_order, id`,
    )
    .all();
  for (const row of rows) {
    console.log(
      `${row.id}\t${row.role}\t${row.display_name}\tport=${row.port ?? "-"}\twd=${row.workdir_relative}`,
    );
  }
}

function cmdSearch(db, query) {
  if (!query) {
    console.error("Usage: boot:search -- <substring>");
    process.exitCode = 1;
    return;
  }
  const like = `%${query}%`;
  const rows = db
    .prepare(
      `SELECT * FROM registered_services
       WHERE enabled = 1 AND (
         id LIKE @q OR display_name LIKE @q OR IFNULL(description,'') LIKE @q
       )
       ORDER BY start_order, id`,
    )
    .all({ q: like });
  for (const row of rows) {
    console.log(`${row.id}\t${row.display_name}`);
  }
}

async function cmdStatus(db) {
  const rows = db
    .prepare(`SELECT * FROM registered_services ORDER BY start_order, id`)
    .all();
  const state = readState();
  for (const row of rows) {
    const tracked = state[row.id];
    const pid = tracked?.pid;
    const pidAlive = isAlive(pid);
    const healthy = await probeHealth(row);
    const runningLabel =
      pidAlive ? `pid=${pid}` : healthy ? "port/listen (no booter pid)" : "stopped";
    console.log(
      `${row.id}\t${row.enabled ? "enabled" : "disabled"}\t${runningLabel}\thealth=${healthy}`,
    );
  }
}

function startOne(row) {
  const cwd = resolveWorkdir(row.workdir_relative);
  if (!fs.existsSync(cwd)) {
    console.error(`Skip ${row.id}: workdir missing: ${cwd}`);
    return;
  }
  const cmd = normalizeCommand(row);
  const args = parseArgs(row);
  const env = { ...process.env, ...parseEnv(row) };
  const child = spawn(cmd, args, {
    cwd,
    env,
    stdio: "inherit",
    detached: false,
  });
  const state = readState();
  state[row.id] = { pid: child.pid, startedAt: new Date().toISOString() };
  writeState(state);
  child.on("exit", (code, signal) => {
    const next = readState();
    if (next[row.id]?.pid === child.pid) {
      delete next[row.id];
      writeState(next);
    }
    console.error(`${row.id} exited code=${code} signal=${signal ?? ""}`);
  });
  console.log(`Started ${row.id} pid=${child.pid} cwd=${cwd}`);
}

function cmdStart(db, ids) {
  const allFlag = ids.includes("--all");
  const want = new Set(ids.filter((x) => x !== "--all"));
  const rows = db
    .prepare(
      `SELECT * FROM registered_services WHERE enabled = 1 ORDER BY start_order, id`,
    )
    .all();
  const picked = allFlag
    ? rows
    : rows.filter((r) => want.has(r.id));
  if (!allFlag && picked.length === 0) {
    console.error("Usage: npm run boot:start -- <id> [<id>...]  or  --all");
    process.exitCode = 1;
    return;
  }
  for (const row of picked) {
    startOne(row);
  }
}

function cmdStop(ids) {
  const state = readState();
  const allFlag = ids.includes("--all");
  const want = new Set(ids.filter((x) => x !== "--all"));
  const targets = allFlag ? Object.keys(state) : [...want];
  for (const id of targets) {
    const entry = state[id];
    if (!entry?.pid) {
      continue;
    }
    try {
      process.kill(entry.pid, "SIGTERM");
      console.log(`Sent SIGTERM to ${id} pid=${entry.pid}`);
    } catch (err) {
      console.error(`Failed to stop ${id}:`, err);
    }
    delete state[id];
  }
  writeState(state);
}

function printUsage() {
  console.log(`Arb Aspire booter — commands:
  init              Create ${REGISTRY_DB} and seed IAM, general AI agent, solutions, storage gRPC, frontend, and Aspire Next dev rows.
  list              List enabled services (start order).
  search <text>     Search id / display name / description.
  status            Show enabled flag, booter-tracked pid, and health probe.
  start <id>|--all  Spawn processes (tracked in .aspire/booter-pids.json).
  stop <id>|--all   SIGTERM tracked pids.

Repo root: ${REPO_ROOT}
Aspire root: ${ASPIRE_ROOT}`);
}

async function main() {
  const [, , command, ...rest] = process.argv;
  if (!command || command === "-h" || command === "--help") {
    printUsage();
    return;
  }

  if (command === "init") {
    cmdInit();
    return;
  }

  if (!fs.existsSync(REGISTRY_DB)) {
    console.error(`Missing ${REGISTRY_DB}. Run: npm run boot:init`);
    process.exitCode = 1;
    return;
  }

  const db = openDb();
  try {
    if (command === "list") {
      cmdList(db);
    } else if (command === "search") {
      cmdSearch(db, rest[0]);
    } else if (command === "status") {
      await cmdStatus(db);
    } else if (command === "start") {
      cmdStart(db, rest);
    } else if (command === "stop") {
      cmdStop(rest);
    } else {
      printUsage();
      process.exitCode = 1;
    }
  } finally {
    db.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
