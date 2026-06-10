import "server-only";

import {
  IamServiceClient,
  IamServiceClientError,
} from "@arb/iam-service-client";

import { IamServiceConfig } from "@/lib/config/iam-service-config";
import type { ArchitectIamRoleSummaryCounts } from "@/lib/types/architect-workspace";

import { mapUserTypeStatsToRolePanels } from "@/lib/iam/map-user-type-stats-to-role-panels";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isUuid(value: string): boolean {
  return UUID_RE.test(value.trim());
}

function mockRolePanels(): ArchitectIamRoleSummaryCounts {
  return {
    admins: 2,
    solutionOwners: 4,
    architects: 3,
    softwareDevs: 6,
    devops: 2,
  };
}

export interface UserTypeStatsForArchitectWorkspace {
  readonly roles: ArchitectIamRoleSummaryCounts;
  readonly entries: readonly { readonly userType: string; readonly count: number }[];
  readonly source: "iam" | "mock";
}

/**
 * Loads IAM `GetUserTypeStats`, maps to the five role panels, and returns JSON-friendly rows
 * (`userType` + `count` per bucket).
 */
export async function loadUserTypeStatsForArchitectWorkspace(): Promise<UserTypeStatsForArchitectWorkspace> {
  if (IamServiceConfig.useListMock) {
    const roles = mockRolePanels();
    const entries = [
      { userType: "Admin", count: roles.admins },
      { userType: "Solution Owner", count: roles.solutionOwners },
      { userType: "Architect", count: roles.architects },
      { userType: "Software Developer", count: roles.softwareDevs },
      { userType: "DevOps", count: roles.devops },
    ].filter((e) => e.count > 0);
    return { roles, entries, source: "mock" };
  }

  const accountId = IamServiceConfig.accountId;
  if (!isUuid(accountId)) {
    throw new Error(
      "IAM_ACCOUNT_ID must be a valid UUID for GetUserTypeStats.",
    );
  }

  const client = new IamServiceClient({
    host: IamServiceConfig.host,
    port: IamServiceConfig.port,
  });
  try {
    const reply = await client.getUserTypeStats({
      accountId,
      includeDeleted: false,
    });
    const entries = reply.entries.map((e) => ({
      userType: e.typeName,
      count: Number(e.count),
    }));
    const roles = mapUserTypeStatsToRolePanels(
      entries.map((x) => ({ typeName: x.userType, count: x.count })),
    );
    return { roles, entries, source: "iam" };
  } catch (err: unknown) {
    if (err instanceof IamServiceClientError) {
      throw new Error(
        `IAM service (${IamServiceConfig.host}:${IamServiceConfig.port}): ${err.message}`,
      );
    }
    throw err;
  } finally {
    client.close();
  }
}
