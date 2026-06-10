import type { AppInfo } from "@/lib/types/app-info";

/** Result shape for loading `registered_services` (server page + server action). */
export type RegisteredServicesLoadResult =
  | { readonly ok: true; readonly services: readonly AppInfo[] }
  | { readonly ok: false; readonly message: string; readonly detail?: string };
