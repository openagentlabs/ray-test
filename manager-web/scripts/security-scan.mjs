#!/usr/bin/env node
/**
 * Runs syft (SBOM), grype (vulnerabilities), and trivy (config/secrets/fs)
 * after production or full builds. Logs land in a folder named after the
 * project root directory (e.g. manager-web/manager-web/).
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(SCRIPT_DIR, "..");
const PROJECT_FOLDER_NAME = path.basename(PROJECT_ROOT);
const SCAN_LOG_ROOT = path.join(PROJECT_ROOT, PROJECT_FOLDER_NAME);

const TOOLS = Object.freeze([
  {
    id: "syft",
    label: "Syft — SBOM extractor (Anchore)",
    command: "syft",
    buildArgs: ({ runDir, stamp }) => ({
      args: [
        `dir:${PROJECT_ROOT}`,
        "-o",
        "json",
        `--output-file=${path.join(runDir, "syft-sbom.json")}`,
      ],
      logName: "syft.log",
      extra: () =>
        runSyftTable(runDir, stamp),
    }),
  },
  {
    id: "grype",
    label: "Grype — vulnerability matcher (Anchore)",
    command: "grype",
    buildArgs: ({ runDir }) => {
      const sbomPath = path.join(runDir, "syft-sbom.json");
      const target = fs.existsSync(sbomPath)
        ? `sbom:${sbomPath}`
        : `dir:${PROJECT_ROOT}`;
      return {
        args: [target, "-o", "json"],
        logName: "grype.log",
        outputFile: path.join(runDir, "grype-report.json"),
        extra: () => runGrypeTable(runDir, target),
      };
    },
  },
  {
    id: "trivy",
    label: "Trivy — vulnerability, config, and secret scanner (Aqua)",
    command: "trivy",
    buildArgs: ({ runDir }) => ({
      args: [
        "fs",
        PROJECT_ROOT,
        "--scanners",
        "vuln,secret,misconfig",
        "--format",
        "json",
        "--output",
        path.join(runDir, "trivy-report.json"),
        "--skip-dirs",
        "node_modules/.cache,.next/cache",
      ],
      logName: "trivy.log",
      extra: () => runTrivyTable(runDir),
    }),
  },
]);

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, "-");
}

function ensureDirectory(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function resolveExecutable(command) {
  const lookup = spawnSync("sh", ["-c", `command -v ${command}`], {
    encoding: "utf8",
  });
  if (lookup.status !== 0) {
    return null;
  }
  const resolved = lookup.stdout.trim();
  return resolved.length > 0 ? resolved : null;
}

function appendLog(logPath, lines) {
  fs.appendFileSync(logPath, `${lines.join("\n")}\n`, "utf8");
}

function runCommand({ executable, args, logPath, label, outputFile }) {
  const startedAt = new Date().toISOString();
  appendLog(logPath, [`[${startedAt}] START ${label}`, `command: ${executable} ${args.join(" ")}`]);

  const result = spawnSync(executable, args, {
    cwd: PROJECT_ROOT,
    encoding: "utf8",
    env: process.env,
  });

  if (outputFile && result.stdout) {
    fs.writeFileSync(outputFile, result.stdout, "utf8");
  }

  if (result.stdout && outputFile === undefined) {
    appendLog(logPath, ["--- stdout ---", result.stdout]);
  } else if (result.stdout && outputFile !== undefined) {
    appendLog(logPath, [`--- stdout written to ${outputFile} ---`]);
  }
  if (result.stderr) {
    appendLog(logPath, ["--- stderr ---", result.stderr]);
  }

  const finishedAt = new Date().toISOString();
  appendLog(logPath, [
    `[${finishedAt}] END ${label}`,
    `exitCode: ${result.status ?? "null"}`,
  ]);

  return {
    ok: result.status === 0,
    exitCode: result.status ?? 1,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
  };
}

function runSyftTable(runDir) {
  const tablePath = path.join(runDir, "syft-sbom.txt");
  const executable = resolveExecutable("syft");
  if (executable === null) {
    return { ok: false, exitCode: 127 };
  }
  return runCommand({
    executable,
    args: [
      `dir:${PROJECT_ROOT}`,
      "-o",
      "table",
      `--output-file=${tablePath}`,
    ],
    logPath: path.join(runDir, "syft.log"),
    label: "syft table",
  });
}

function runGrypeTable(runDir, target) {
  const tablePath = path.join(runDir, "grype-report.txt");
  const executable = resolveExecutable("grype");
  if (executable === null) {
    return { ok: false, exitCode: 127 };
  }
  return runCommand({
    executable,
    args: [target, "-o", "table"],
    logPath: path.join(runDir, "grype.log"),
    label: "grype table",
    outputFile: tablePath,
  });
}

function runTrivyTable(runDir) {
  const tablePath = path.join(runDir, "trivy-report.txt");
  const executable = resolveExecutable("trivy");
  if (executable === null) {
    return { ok: false, exitCode: 127 };
  }
  return runCommand({
    executable,
    args: [
      "fs",
      PROJECT_ROOT,
      "--scanners",
      "vuln,secret,misconfig",
      "--format",
      "table",
      "--output",
      tablePath,
      "--skip-dirs",
      "node_modules/.cache,.next/cache",
    ],
    logPath: path.join(runDir, "trivy.log"),
    label: "trivy table",
  });
}

function printInstallHelp(missingTools) {
  const lines = [
    "",
    "Security scan tools are required for production / full builds.",
    `Missing: ${missingTools.join(", ")}`,
    "",
    "Install (examples):",
    "  # Aqua Trivy — https://trivy.dev/latest/getting-started/installation/",
    "  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sudo sh -s -- -b /usr/local/bin",
    "",
    "  # Syft — https://github.com/anchore/syft#installation",
    "  curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sudo sh -s -- -b /usr/local/bin",
    "",
    "  # Grype — https://github.com/anchore/grype#installation",
    "  curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sudo sh -s -- -b /usr/local/bin",
    "",
    "Fast builds without scans: npm run build:fast",
    "Skip scans explicitly: MANAGER_WEB_SKIP_SECURITY_SCAN=1 npm run build",
    "",
  ];
  process.stderr.write(lines.join("\n"));
}

function main() {
  if (process.env.MANAGER_WEB_SKIP_SECURITY_SCAN === "1") {
    process.stdout.write(
      "security-scan: skipped (MANAGER_WEB_SKIP_SECURITY_SCAN=1)\n",
    );
    return;
  }

  const missingTools = TOOLS.map((tool) => tool.command).filter(
    (command) => resolveExecutable(command) === null,
  );

  if (missingTools.length > 0) {
    printInstallHelp(missingTools);
    process.exit(1);
  }

  ensureDirectory(SCAN_LOG_ROOT);
  const stamp = timestampSlug();
  const runDir = path.join(SCAN_LOG_ROOT, stamp);
  ensureDirectory(runDir);

  const summaryPath = path.join(runDir, "summary.log");
  appendLog(summaryPath, [
    `projectRoot: ${PROJECT_ROOT}`,
    `projectFolderName: ${PROJECT_FOLDER_NAME}`,
    `scanLogRoot: ${SCAN_LOG_ROOT}`,
    `runDirectory: ${runDir}`,
    `startedAt: ${new Date().toISOString()}`,
    "",
  ]);

  const results = [];

  for (const tool of TOOLS) {
    const executable = resolveExecutable(tool.command);
    const { args, logName, extra, outputFile } = tool.buildArgs({ runDir, stamp });
    const logPath = path.join(runDir, logName);

    process.stdout.write(`security-scan: running ${tool.label}\n`);

    const primary = runCommand({
      executable,
      args,
      logPath,
      label: tool.id,
      outputFile,
    });

    let secondary = { ok: true, exitCode: 0 };
    if (typeof extra === "function") {
      secondary = extra();
    }

    const ok = primary.ok && secondary.ok;
    results.push({
      id: tool.id,
      ok,
      exitCode: ok ? 0 : primary.exitCode || secondary.exitCode,
    });

    appendLog(summaryPath, [
      `${tool.id}: ${ok ? "PASS" : "FAIL"} (exit ${primary.exitCode})`,
    ]);
  }

  appendLog(summaryPath, [
    "",
    `finishedAt: ${new Date().toISOString()}`,
    `overall: ${results.every((entry) => entry.ok) ? "PASS" : "FAIL"}`,
  ]);

  process.stdout.write(`security-scan: logs written to ${runDir}\n`);

  const failed = results.filter((entry) => !entry.ok);
  if (failed.length > 0) {
    process.stderr.write(
      `security-scan: failed tools: ${failed.map((entry) => entry.id).join(", ")}\n`,
    );
    process.exit(1);
  }
}

main();
