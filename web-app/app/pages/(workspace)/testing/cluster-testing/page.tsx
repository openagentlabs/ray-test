import type { Metadata } from "next";

import {
  buildMountTestTargets,
  ClusterTestingPage,
} from "@/pages-components/testing/cluster-testing-page";

export const metadata: Metadata = {
  title: "Mount testing",
  description:
    "Validate FSx for Lustre and shared S3 file system mounts with write, verify, and cleanup tests.",
};

export default function ClusterTestingRoute() {
  const { lustreTarget, s3SharedFilesTarget } = buildMountTestTargets();

  return (
    <ClusterTestingPage
      lustreTarget={lustreTarget}
      s3SharedFilesTarget={s3SharedFilesTarget}
    />
  );
}
