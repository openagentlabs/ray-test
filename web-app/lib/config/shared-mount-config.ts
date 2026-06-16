/**
 * Shared filesystem mount paths for manager-web container workloads.
 * Volume names and default paths match infra/aws/aws_tf/modules/lustre_shared_mount
 * and infra/aws/aws_tf/modules/s3_shared_mount.
 */
export type SharedMountKind = "lustre" | "s3-shared-files";

export interface SharedMountDefinition {
  readonly kind: SharedMountKind;
  readonly volumeName: string;
  readonly mountPath: string;
  readonly displayName: string;
}

export class SharedMountConfig {
  public static readonly lustre: SharedMountDefinition = Object.freeze({
    kind: "lustre",
    volumeName:
      process.env.LUSTRE_VOLUME_NAME ?? "shared-lustre",
    mountPath:
      process.env.LUSTRE_MOUNT_PATH ??
      process.env.CLUSTER_MOUNT_PATH ??
      "/mnt/lustre",
    displayName: "Lustre",
  });

  public static readonly s3SharedFiles: SharedMountDefinition = Object.freeze({
    kind: "s3-shared-files",
    volumeName:
      process.env.S3_SHARED_VOLUME_NAME ?? "shared-s3-files",
    mountPath:
      process.env.S3_SHARED_MOUNT_PATH ??
      process.env.S3_SHARED_FILES_MOUNT_PATH ??
      "/mnt/s3-files",
    displayName: "S3 shared files",
  });

  public static readonly all: readonly SharedMountDefinition[] = Object.freeze([
    SharedMountConfig.lustre,
    SharedMountConfig.s3SharedFiles,
  ]);

  public static get(kind: SharedMountKind): SharedMountDefinition {
    if (kind === "lustre") {
      return SharedMountConfig.lustre;
    }
    return SharedMountConfig.s3SharedFiles;
  }

  private constructor() {}
}
