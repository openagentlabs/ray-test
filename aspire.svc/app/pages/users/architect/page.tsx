import { ArchitectWorkspacePage } from "@/components/pages/architect-workspace/architect-workspace-page";
import { RegisteredServicesLoader } from "@/lib/services/registered-services-loader";

export default async function AspireUsersArchitectPage() {
  const registeredServicesBootstrap = RegisteredServicesLoader.safeLoad();

  return (
    <ArchitectWorkspacePage registeredServicesBootstrap={registeredServicesBootstrap} />
  );
}
