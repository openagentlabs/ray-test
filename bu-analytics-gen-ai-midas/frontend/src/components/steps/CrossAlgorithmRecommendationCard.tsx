import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle, Loader, RefreshCw, Sparkles } from 'lucide-react';
import { fastApiService } from '../../services/fastApiService';
import { buildStep6CrossAlgorithmPayload } from './step6CrossAlgorithmPayload';

type Props = {
  datasetId?: string | null;
  problemType: string;
  results: any;
  g1Rows: any[];
  g2Rows: any[];
  lrRows: any[];
  /** Distinguishes auto vs manual Step 6 panels for in-memory fetch de-duplication. */
  variant: 'auto' | 'manual';
};

type Phase = 'idle' | 'loading' | 'ready' | 'error';

/** Strip markdown-style `**` from LLM summaries (plain text UI). */
export function stripCrossAlgorithmMarkdownArtifacts(raw: string): string {
  if (!raw) return raw;
  let s = raw.replace(/\*\*([^*]+)\*\*/g, '$1');
  s = s.replace(/\*\*/g, '');
  return s;
}

export const CrossAlgorithmRecommendationCard: React.FC<Props> = ({
  datasetId,
  problemType,
  results,
  g1Rows,
  g2Rows,
  lrRows,
  variant,
}) => {
  const [phase, setPhase] = useState<Phase>('idle');
  const [summary, setSummary] = useState('');
  const [error, setError] = useState<string | null>(null);

  const payload = useMemo(
    () => buildStep6CrossAlgorithmPayload(results, g1Rows, g2Rows, lrRows, problemType),
    [results, g1Rows, g2Rows, lrRows, problemType],
  );

  const requestFingerprint = useMemo(() => {
    if (!payload) return '';
    try {
      return JSON.stringify({
        v: variant,
        c: payload.candidates,
        l: payload.lr_digest,
        pt: problemType,
      });
    } catch {
      return `${variant}:${payload.candidates.length}`;
    }
  }, [payload, variant, problemType]);

  useEffect(() => {
    if (!datasetId || !payload || payload.candidates.length === 0) {
      setPhase('idle');
      setSummary('');
      setError(null);
      return;
    }

    let cancelled = false;
    const run = async () => {
      setPhase('loading');
      setError(null);
      try {
        const res = await fastApiService.crossAlgorithmRecommendation(datasetId, {
          problem_type: problemType || 'classification',
          candidates: payload.candidates,
          lr_digest: payload.lr_digest.length ? payload.lr_digest : undefined,
        });
        if (cancelled) return;
        if (res.success && res.summary) {
          setSummary(stripCrossAlgorithmMarkdownArtifacts(res.summary));
          setPhase('ready');
        } else {
          setError(res.error || 'No summary returned.');
          setPhase('error');
        }
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Request failed');
        setPhase('error');
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [datasetId, requestFingerprint, problemType]);

  if (!datasetId || !payload || payload.candidates.length === 0) {
    return null;
  }

  const onRetry = () => {
    if (!datasetId || !payload) return;
    setPhase('loading');
    setError(null);
    fastApiService
      .crossAlgorithmRecommendation(datasetId, {
        problem_type: problemType || 'classification',
        candidates: payload.candidates,
        lr_digest: payload.lr_digest.length ? payload.lr_digest : undefined,
      })
      .then((res) => {
        if (res.success && res.summary) {
          setSummary(stripCrossAlgorithmMarkdownArtifacts(res.summary));
          setPhase('ready');
        } else {
          setError(res.error || 'No summary returned.');
          setPhase('error');
        }
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'Request failed');
        setPhase('error');
      });
  };

  return (
    <div className="mb-5 border border-emerald-200/80 dark:border-emerald-800/60 rounded-lg p-4 bg-white dark:bg-slate-900/60 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <Sparkles className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden />
          <div>
            <div className="text-sm font-semibold text-gray-900 dark:text-white">Cross-algorithm recommendation</div>
            <div className="text-[11px] text-gray-500 dark:text-gray-400">Best model across all algorithms</div>
          </div>
        </div>
        <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200 border border-amber-200/80 dark:border-amber-800/60 shrink-0">
          AI recommendation
        </span>
      </div>

      {phase === 'loading' && (
        <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 py-6 justify-center">
          <Loader className="h-4 w-4 animate-spin text-emerald-600" aria-hidden />
          Generating summary…
        </div>
      )}

      {phase === 'ready' && summary && (
        <div className="rounded-lg border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/70 dark:bg-emerald-950/30 p-3 flex gap-2">
          <CheckCircle className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" aria-hidden />
          <p className="text-xs sm:text-sm text-gray-800 dark:text-gray-100 leading-relaxed whitespace-pre-wrap">
            {summary}
          </p>
        </div>
      )}

      {phase === 'error' && (
        <div className="rounded-lg border border-rose-200 dark:border-rose-900/50 bg-rose-50/80 dark:bg-rose-950/30 p-3 text-xs text-rose-800 dark:text-rose-200 flex flex-wrap items-center gap-2 justify-between">
          <span>{error || 'Something went wrong.'}</span>
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-rose-300 dark:border-rose-800 text-rose-900 dark:text-rose-100 hover:bg-rose-100/80 dark:hover:bg-rose-900/40 text-[11px] font-medium"
          >
            <RefreshCw className="h-3 w-3" aria-hidden />
            Retry
          </button>
        </div>
      )}
    </div>
  );
};

export default CrossAlgorithmRecommendationCard;
