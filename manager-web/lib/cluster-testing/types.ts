export type ClusterTestStepStatus = "pending" | "running" | "success" | "failure";

export interface ClusterTestStep {
  readonly id: string;
  readonly label: string;
  readonly status: ClusterTestStepStatus;
  readonly detail?: string;
}

export interface ClusterMountTestResult {
  readonly mountKind: string;
  readonly volumeName: string;
  readonly displayName: string;
  readonly mountPath: string;
  readonly testFilePath: string;
  readonly steps: readonly ClusterTestStep[];
  readonly logs: readonly string[];
  readonly startedAt: string;
  readonly completedAt: string;
  readonly overallSuccess: boolean;
}
