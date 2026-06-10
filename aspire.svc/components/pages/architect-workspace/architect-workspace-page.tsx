import type { RegisteredServicesLoadResult } from "@/lib/types/registered-services-load-result";

import { ArchitectWorkspaceMock } from "./architect-workspace-mock";

export function ArchitectWorkspacePage({
  registeredServicesBootstrap,
}: {
  readonly registeredServicesBootstrap: RegisteredServicesLoadResult;
}) {
  return (
    <ArchitectWorkspaceMock registeredServicesBootstrap={registeredServicesBootstrap} />
  );
}
