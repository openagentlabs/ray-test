import { ServerCog } from "lucide-react";

import { SharedMountConfig } from "@/lib/config/shared-mount-config";
import {
  MountTestSection,
  type MountTestTarget,
} from "@/pages-components/testing/mount-test-section";

interface ClusterTestingPageProps {
  readonly lustreTarget: MountTestTarget;
  readonly s3SharedFilesTarget: MountTestTarget;
}

export function ClusterTestingPage({
  lustreTarget,
  s3SharedFilesTarget,
}: ClusterTestingPageProps) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-12">
      <header className="flex flex-col gap-2">
        <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-border bg-muted/60 px-3 py-1 text-xs font-medium text-muted-foreground">
          <ServerCog className="size-3.5 text-primary" aria-hidden />
          Shared filesystem mounts
        </span>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          Mount testing
        </h1>
        <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
          Validate container mount points for the shared Lustre and S3-backed
          file systems. Each section runs the same write, verify, and cleanup
          workflow against its configured mount path using the file-system
          client.
        </p>
      </header>

      <MountTestSection
        target={lustreTarget}
        badge="FSx for Lustre · shared-lustre"
        description="Exercise the FSx for Lustre shared mount. The test validates the container mount path, writes a 512 MB binary file, verifies access through Cluster, then removes the artefact."
      />

      <div className="border-t border-border" aria-hidden />

      <MountTestSection
        target={s3SharedFilesTarget}
        badge="Mountpoint for Amazon S3 · shared-s3-files"
        description="Exercise the shared S3-backed file system mount. The test uses the same workflow as Lustre: validate the mount path, write a 512 MB binary file, verify through Cluster, then delete the test file."
      />
    </div>
  );
}

export function buildMountTestTargets() {
  return {
    lustreTarget: toMountTestTarget(SharedMountConfig.lustre),
    s3SharedFilesTarget: toMountTestTarget(SharedMountConfig.s3SharedFiles),
  };
}

function toMountTestTarget(
  mount: (typeof SharedMountConfig)["lustre"],
): MountTestTarget {
  return {
    kind: mount.kind,
    volumeName: mount.volumeName,
    mountPath: mount.mountPath,
    displayName: mount.displayName,
  };
}
