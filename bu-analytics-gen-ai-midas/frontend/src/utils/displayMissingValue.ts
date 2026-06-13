const DASH_PLACEHOLDER = '-';
const DEFAULT_EMPTY_LABEL = 'NA';

export const isMissingValue = (value: number | string | undefined | null): boolean => {
  if (value === undefined || value === null) return true;
  if (typeof value === 'string') {
    return value.trim() === DASH_PLACEHOLDER;
  }
  return false;
};

export const parseNumericValue = (value: number | string | undefined | null): number | undefined => {
  if (value === undefined || value === null) return undefined;
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : undefined;
  }
  if (typeof value === 'string') {
    if (value.trim() === DASH_PLACEHOLDER) return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
};

export const formatAsPercent = (
  value: number | string | undefined | null,
  decimals = 2,
  fallback = DEFAULT_EMPTY_LABEL
): string => {
  const numeric = parseNumericValue(value);
  if (numeric === undefined) return fallback;
  return `${(numeric * 100).toFixed(decimals)}%`;
};

export const formatAsDecimal = (
  value: number | string | undefined | null,
  decimals = 4,
  fallback = DEFAULT_EMPTY_LABEL
): string => {
  const numeric = parseNumericValue(value);
  if (numeric === undefined) return fallback;
  return numeric.toFixed(decimals);
};

export const formatTrainTestPair = (
  trainValue: number | string | undefined | null,
  testValue: number | string | undefined | null,
  formatter: (value: number) => string,
  fallback = DEFAULT_EMPTY_LABEL
): string => {
  const parsedTrain = parseNumericValue(trainValue);
  const parsedTest = parseNumericValue(testValue);

  if (parsedTrain !== undefined && parsedTest !== undefined) {
    return `${formatter(parsedTrain)} / ${formatter(parsedTest)}`;
  }
  if (parsedTrain !== undefined) {
    return `${formatter(parsedTrain)} / ${fallback}`;
  }
  if (parsedTest !== undefined) {
    return formatter(parsedTest);
  }
  return fallback;
};
