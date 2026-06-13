import {
  closeSync,
  openSync,
  statSync,
  unlinkSync,
  writeSync,
} from "node:fs";
import { join } from "node:path";

import { Cluster } from "@/lib/file-system";
import {
  SharedMountConfig,
  type SharedMountKind,
} from "@/lib/config/shared-mount-config";
import { probeSharedMount } from "@/lib/mount/shared-mount-health";
import type {
  ClusterMountTestResult,
  ClusterTestStep,
  ClusterTestStepStatus,
} from "@/lib/cluster-testing/types";

const TEST_FILE_BYTES = 512 * 1024 * 1024;
const WRITE_CHUNK_BYTES = 4 * 1024 * 1024;

interface MutableStep extends ClusterTestStep {
  status: ClusterTestStepStatus;
  detail?: string;
}

export async function runClusterMountTest(
  mountKind: SharedMountKind,
  onProgress?: (snapshot: ClusterMountTestResult) => void | Promise<void>,
): Promise<ClusterMountTestResult> {
  const mount = SharedMountConfig.get(mountKind);
  const startedAt = new Date().toISOString();
  const mountPath = mount.mountPath;
  const testFilePrefix =
    mountKind === "lustre" ? ".lustre-mount-test-" : ".s3-shared-mount-test-";
  const testFilePath = join(mountPath, `${testFilePrefix}${Date.now()}.bin`);
  const cluster = new Cluster();
  const logs: string[] = [];
  const steps: MutableStep[] = createDefaultSteps(mount.displayName);

  const logEntry = (message: string) => {
    const entry = `[${new Date().toISOString()}] ${message}`;
    logs.push(entry);
    void emitProgress(false);
  };

  const emitProgress = async (overallSuccess: boolean) => {
    if (onProgress === undefined) {
      return;
    }
    await onProgress(buildSnapshot(mount, {
      mountPath,
      testFilePath,
      steps,
      logs,
      startedAt,
      overallSuccess,
    }));
  };

  const setStep = (
    id: string,
    status: ClusterTestStepStatus,
    detail?: string,
  ) => {
    const step = steps.find((item) => item.id === id);
    if (step === undefined) {
      return;
    }
    step.status = status;
    step.detail = detail;
    void emitProgress(false);
  };

  let fileDescriptor: number | undefined;

  const failStep = (id: string, detail: string) => {
    setStep(id, "failure", detail);
    logEntry(`FAIL ${id}: ${detail}`);
  };

  function log(message: string) {
    logEntry(message);
  }

  try {
    log(`Volume: ${mount.volumeName}`);
    log(`Mount kind: ${mount.kind}`);
    setStep("validate-mount", "running");
    log(`Checking ${mount.displayName} mount path: ${mountPath}`);
    const probe = await probeSharedMount(mount);
    if (!probe.ok) {
      failStep("validate-mount", probe.detail);
      return finalize({
        mount,
        startedAt,
        mountPath,
        testFilePath,
        steps,
        logs,
        overallSuccess: false,
        onProgress,
      });
    }
    setStep(
      "validate-mount",
      "success",
      `${mount.displayName} mount point found at ${mountPath}`,
    );
    log(probe.detail);

    setStep("open-file", "running");
    log(`Opening test file: ${testFilePath}`);
    try {
      fileDescriptor = openSync(testFilePath, "w");
      setStep("open-file", "success", `File descriptor ${fileDescriptor} opened`);
      log(`Opened file descriptor ${fileDescriptor}`);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Could not open test file";
      failStep("open-file", message);
      return finalize({
        mount,
        startedAt,
        mountPath,
        testFilePath,
        steps,
        logs,
        overallSuccess: false,
        onProgress,
      });
    }

    setStep("write-file", "running");
    log(`Writing ${TEST_FILE_BYTES} bytes in ${WRITE_CHUNK_BYTES}-byte chunks`);
    try {
      const chunk = Buffer.alloc(WRITE_CHUNK_BYTES, 0x5a);
      let bytesWritten = 0;
      while (bytesWritten < TEST_FILE_BYTES) {
        const remaining = TEST_FILE_BYTES - bytesWritten;
        const chunkSize = Math.min(WRITE_CHUNK_BYTES, remaining);
        const written = writeSync(
          fileDescriptor,
          chunk.subarray(0, chunkSize),
        );
        if (written <= 0) {
          throw new Error("Write returned zero bytes");
        }
        bytesWritten += written;
        if (bytesWritten % (64 * 1024 * 1024) === 0) {
          log(`Progress: ${bytesWritten}/${TEST_FILE_BYTES} bytes written`);
        }
      }
      setStep(
        "write-file",
        "success",
        `Wrote ${bytesWritten.toLocaleString()} bytes`,
      );
      log(`Write complete (${bytesWritten} bytes)`);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Write operation failed";
      failStep("write-file", message);
      return finalize({
        mount,
        startedAt,
        mountPath,
        testFilePath,
        steps,
        logs,
        overallSuccess: false,
        fileDescriptor,
        onProgress,
      });
    }

    setStep("close-file", "running");
    log("Closing test file descriptor");
    try {
      closeSync(fileDescriptor);
      fileDescriptor = undefined;
      setStep("close-file", "success", "File descriptor closed");
      log("File descriptor closed");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Could not close test file";
      failStep("close-file", message);
      return finalize({
        mount,
        startedAt,
        mountPath,
        testFilePath,
        steps,
        logs,
        overallSuccess: false,
        onProgress,
      });
    }

    setStep("verify-file", "running");
    log("Verifying file size via stat and Cluster client probe");
    const fileStat = statSync(testFilePath);
    if (fileStat.size !== TEST_FILE_BYTES) {
      failStep(
        "verify-file",
        `Expected ${TEST_FILE_BYTES} bytes, got ${fileStat.size}`,
      );
      return finalize({
        mount,
        startedAt,
        mountPath,
        testFilePath,
        steps,
        logs,
        overallSuccess: false,
        onProgress,
      });
    }

    const probePath = join(
      mountPath,
      `${mountKind === "lustre" ? ".lustre-probe-" : ".s3-shared-probe-"}${Date.now()}.bin`,
    );
    const probePayload = Buffer.from([0x63, 0x6c, 0x75, 0x73, 0x74, 0x65, 0x72]);
    const probeWrite = cluster.writeBytes(probePath, probePayload);
    if (probeWrite.isErr()) {
      failStep("verify-file", probeWrite.error.message);
      return finalize({
        mount,
        startedAt,
        mountPath,
        testFilePath,
        steps,
        logs,
        overallSuccess: false,
        onProgress,
      });
    }
    const probeRead = cluster.readBytes(probePath);
    unlinkSync(probePath);
    if (probeRead.isErr()) {
      failStep("verify-file", probeRead.error.message);
      return finalize({
        mount,
        startedAt,
        mountPath,
        testFilePath,
        steps,
        logs,
        overallSuccess: false,
        onProgress,
      });
    }
    if (!probeRead.value.equals(probePayload)) {
      failStep("verify-file", "Cluster client probe read did not match payload");
      return finalize({
        mount,
        startedAt,
        mountPath,
        testFilePath,
        steps,
        logs,
        overallSuccess: false,
        onProgress,
      });
    }
    setStep(
      "verify-file",
      "success",
      `Confirmed ${fileStat.size.toLocaleString()} bytes on mount; Cluster probe read/write OK`,
    );
    log("File size and Cluster client probe verified");

    setStep("delete-file", "running");
    log(`Deleting test file: ${testFilePath}`);
    try {
      unlinkSync(testFilePath);
      setStep("delete-file", "success", "Test file removed");
      log("Test file deleted");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Could not delete test file";
      failStep("delete-file", message);
      return finalize({
        mount,
        startedAt,
        mountPath,
        testFilePath,
        steps,
        logs,
        overallSuccess: false,
        onProgress,
      });
    }

    return finalize({
      mount,
      startedAt,
      mountPath,
      testFilePath,
      steps,
      logs,
      overallSuccess: true,
      onProgress,
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unexpected mount test error";
    log(`Unexpected error: ${message}`);
    const runningStep = steps.find((step) => step.status === "running");
    if (runningStep !== undefined) {
      failStep(runningStep.id, message);
    }
    return finalize({
      mount,
      startedAt,
      mountPath,
      testFilePath,
      steps,
      logs,
      overallSuccess: false,
      fileDescriptor,
      onProgress,
    });
  }
}

function createDefaultSteps(displayName: string): MutableStep[] {
  return [
    {
      id: "validate-mount",
      label: `Validate ${displayName} mount point exists`,
      status: "pending",
    },
    {
      id: "open-file",
      label: `Open test file on ${displayName} mount`,
      status: "pending",
    },
    {
      id: "write-file",
      label: `Write 512 MB binary file to ${displayName} mount`,
      status: "pending",
    },
    {
      id: "close-file",
      label: "Close test file",
      status: "pending",
    },
    {
      id: "verify-file",
      label: "Verify written file size via Cluster client",
      status: "pending",
    },
    {
      id: "delete-file",
      label: `Delete test file from ${displayName} mount`,
      status: "pending",
    },
  ];
}

interface SnapshotParts {
  readonly mountPath: string;
  readonly testFilePath: string;
  readonly steps: MutableStep[];
  readonly logs: string[];
  readonly startedAt: string;
  readonly overallSuccess: boolean;
}

function buildSnapshot(
  mount: ReturnType<typeof SharedMountConfig.get>,
  parts: SnapshotParts,
): ClusterMountTestResult {
  return {
    mountKind: mount.kind,
    volumeName: mount.volumeName,
    displayName: mount.displayName,
    mountPath: parts.mountPath,
    testFilePath: parts.testFilePath,
    steps: parts.steps.map((step) => ({ ...step })),
    logs: [...parts.logs],
    startedAt: parts.startedAt,
    completedAt: new Date().toISOString(),
    overallSuccess: parts.overallSuccess,
  };
}

interface FinalizeInput extends SnapshotParts {
  readonly mount: ReturnType<typeof SharedMountConfig.get>;
  readonly fileDescriptor?: number;
  readonly onProgress?: (snapshot: ClusterMountTestResult) => void | Promise<void>;
}

function finalize({
  mount,
  startedAt,
  mountPath,
  testFilePath,
  steps,
  logs,
  overallSuccess,
  fileDescriptor,
  onProgress,
}: FinalizeInput): ClusterMountTestResult {
  if (fileDescriptor !== undefined) {
    try {
      closeSync(fileDescriptor);
      logs.push(`[${new Date().toISOString()}] Closed file descriptor on cleanup`);
    } catch {
      logs.push(`[${new Date().toISOString()}] Failed to close file descriptor on cleanup`);
    }
  }

  if (!overallSuccess) {
    try {
      unlinkSync(testFilePath);
      logs.push(`[${new Date().toISOString()}] Removed test file on cleanup`);
    } catch {
      // Best-effort cleanup only.
    }
  }

  for (const step of steps) {
    if (step.status === "pending" || step.status === "running") {
      step.status = "failure";
      step.detail ??= "Step did not complete";
    }
  }

  const result = buildSnapshot(mount, {
    mountPath,
    testFilePath,
    steps,
    logs,
    startedAt,
    overallSuccess,
  });

  void onProgress?.(result);
  return result;
}
