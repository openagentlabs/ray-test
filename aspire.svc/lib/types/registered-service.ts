/** Serializable row returned by `getServices` (mirrors `registered_services`). */

export interface RegisteredServiceDto {
  readonly id: string;
  readonly displayName: string;
  readonly role: string;
  readonly kind: string;
  readonly workdirRelative: string;
  /** Resolved absolute working directory for the service (repo root + `workdirRelative`). */
  readonly workdirAbsolutePath: string;
  readonly command: string;
  readonly argsJson: string;
  readonly port: number | null;
  readonly healthKind: string;
  readonly healthTarget: string | null;
  readonly description: string;
  readonly startOrder: number;
  readonly enabled: boolean;
  /** When true, the home page may auto-spawn this service once per browser session (Aspire → frontend). */
  readonly autoStartWithHome: boolean;
  readonly envJson: string | null;
}
