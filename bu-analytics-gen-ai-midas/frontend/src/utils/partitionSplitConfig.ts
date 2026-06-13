/** Partition / split configuration for platform_split ingestion (Step 1). */

export type SplitMethod = 'user_identifier' | 'stratified_random' | 'time_based';

export type PartitionKey = 'train' | 'test' | 'validation';

export interface SplitRatios {
  train: number;
  test: number;
  validation: number;
}

/** Identifier mapping for user_identifier split method. */
export interface IdentifierMapping {
  train?: string;
  test?: string;
  /** Validation can be multiple values (up to 3). */
  validation?: string[];
}

export interface SplitConfiguration {
  ingestion_mode: 'platform_split';
  split_method: SplitMethod;
  identifier_column?: string | null;
  /** Maps partition → raw column value(s). Validation supports multiple values. */
  identifier_mapping?: IdentifierMapping | null;
  null_rows_excluded?: number;
  ratios?: SplitRatios | null;
  seed?: number | null;
  date_column?: string | null;
  /** Time-based split: manual Train/Test cutoff date (ISO string). */
  cutoff_1?: string | null;
  /** Time-based split: manual Test/Holdout cutoff date (ISO string). */
  cutoff_2?: string | null;
}

export const TRAIN_ALIASES = ['train', 'training', 'learn', 'fit', 'build'];
export const TEST_ALIASES = ['test', 'testing', 'eval'];
export const VALIDATION_ALIASES = ['validation', 'val', 'validate', 'holdout', 'hold_out', 'oot', 'out_of_time', 'final', 'reserve'];

export function normalizeIdentifierToken(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[\s_-]+/g, '');
}

function matchesAlias(normalized: string, aliases: string[]): boolean {
  return aliases.some((a) => normalized === normalizeIdentifierToken(a));
}

/** Auto-map a single raw unique value to a partition, or null if unknown. */
export function fuzzyMapValueToPartition(raw: string): PartitionKey | null {
  const n = normalizeIdentifierToken(String(raw));
  if (!n || n === 'nan' || n === 'null' || n === 'none') return null;
  if (matchesAlias(n, TRAIN_ALIASES)) return 'train';
  if (matchesAlias(n, TEST_ALIASES)) return 'test';
  if (matchesAlias(n, VALIDATION_ALIASES)) return 'validation';
  return null;
}

export function buildDefaultIdentifierMapping(uniqueValues: string[]): IdentifierMapping {
  const out: IdentifierMapping = {};
  const validationValues: string[] = [];
  
  for (const v of uniqueValues) {
    const p = fuzzyMapValueToPartition(v);
    if (p === 'train' && !out.train) {
      out.train = v;
    } else if (p === 'test' && !out.test) {
      out.test = v;
    } else if (p === 'validation') {
      validationValues.push(v);
    }
  }
  
  if (validationValues.length > 0) {
    out.validation = validationValues.slice(0, 3);
  }
  
  return out;
}

export function createDefaultSplitConfiguration(): SplitConfiguration {
  return {
    ingestion_mode: 'platform_split',
    split_method: 'stratified_random',
    identifier_column: null,
    identifier_mapping: {},
    null_rows_excluded: 0,
    ratios: { train: 60, test: 20, validation: 20 },
    seed: null,
    date_column: null,
  };
}
