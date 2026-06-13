import React, { useEffect, useRef, useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { Image as ImageIcon, Loader, AlertTriangle, Maximize2, X, FileDown } from 'lucide-react';
import { multicollinearityService } from '../services/multicollinearityService';
import {
  downloadExcelWorkbookWithCharts,
  imageUrlToExcelImage,
  type ReportCell,
} from '../utils/excelReportWithCharts';

function correlationMatrixMethodologyAoA(): (string | number)[][] {
  return [
    ['Section', 'Detail'],
    [
      'Numeric feature–feature matrix',
      'Pairwise correlations between all numeric columns using pandas DataFrame.corr() (default Pearson; Spearman selectable on the API). Rows/columns dropped: all-NaN numeric columns, ID-like columns (unique non-null count = row count), zero-variance columns, and the target variable when it is numeric so the matrix reflects predictors only.',
    ],
    [
      'Categorical association heatmap (sidebar)',
      "Pairwise Cramér's V (0–1) from chi-square independence tests on contingency tables. Only categorical columns with 2–35 distinct levels are kept (after removing ID-like columns and optionally the target). The heatmap image shows the top N columns (5, 10, 15, or 20) by maximum off-diagonal association.",
    ],
    [
      'Workbook',
      'This export contains Methodology, Report info, Full matrix, and numeric/categorical heatmap images when those images are loaded in the UI.',
    ],
  ];
}

function correlationDictToSquareGrid(cm: Record<string, Record<string, number>>): (string | number)[][] {
  const cols = Object.keys(cm).sort((a, b) => a.localeCompare(b));
  if (!cols.length) return [['(empty matrix)']];
  const header: (string | number)[] = ['', ...cols];
  const rows: (string | number)[][] = [header];
  for (const r of cols) {
    const inner = cm[r] || {};
    const row: (string | number)[] = [r];
    for (const c of cols) {
      const v = inner[c];
      row.push(typeof v === 'number' && !Number.isNaN(v) ? v : '');
    }
    rows.push(row);
  }
  return rows;
}

interface MulticollinearityAnalysisComponentProps {
  datasetId: string | null;
  targetVariable?: string | null;
  currentStep?: number; // default 3
}

// Simple cache by dataset-target-scope to avoid refetch within session
const heatmapCache = new Map<string, { numeric: string; categorical: string | null; ts: number }>();
const CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes

const MulticollinearityAnalysisComponent: React.FC<MulticollinearityAnalysisComponentProps> = ({
  datasetId,
  targetVariable,
  currentStep = 3,
}) => {
  const { isDark } = useTheme();
  const [uri, setUri] = useState<string | null>(null);
  const [catUri, setCatUri] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** Which heatmap is expanded (same modal layout as original single-chart version) */
  const [expandedKind, setExpandedKind] = useState<null | 'numeric' | 'categorical'>(null);
  const [isExcelDownloading, setIsExcelDownloading] = useState(false);
  const [topFeaturesNumeric, setTopFeaturesNumeric] = useState<number>(20);
  const [topFeaturesCategorical, setTopFeaturesCategorical] = useState<number>(20);
  const mountedRef = useRef(true);
  const blobUrlRefNumeric = useRef<string | null>(null);
  const blobUrlRefCat = useRef<string | null>(null);
  const triedBlobNumericRef = useRef(false);
  const triedBlobCatRef = useRef(false);
  const isLoadingRef = useRef(false);

  // Fallback to session storage if props not provided
  const effectiveDatasetId = datasetId || (typeof window !== 'undefined' ? sessionStorage.getItem('dataset_id') : null);
  const effectiveTargetVar = targetVariable || (typeof window !== 'undefined' ? ((): string | null => {
    try {
      const raw = sessionStorage.getItem('dataset_config');
      if (!raw) return null;
      const cfg = JSON.parse(raw);
      return cfg?.target_variable || null;
    } catch {
      return null;
    }
  })() : null);

  // Get current data scope from sessionStorage
  const getDataScope = () => {
    try {
      const cfg = sessionStorage.getItem('dataset_config');
      if (cfg) {
        const parsed = JSON.parse(cfg);
        return parsed?.data_scope || 'entire';
      }
    } catch (e) {
      console.error('Error reading data scope:', e);
    }
    return 'entire';
  };

  const dataScope = getDataScope();
  // Cache key excludes currentStep - data is step-independent
  const cacheKey = `${effectiveDatasetId || 'none'}-${effectiveTargetVar || 'none'}-multicollinearity-${dataScope}-${isDark ? 'dark' : 'light'}-num${topFeaturesNumeric}-cat${topFeaturesCategorical}`;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (blobUrlRefNumeric.current) {
        URL.revokeObjectURL(blobUrlRefNumeric.current);
        blobUrlRefNumeric.current = null;
      }
      if (blobUrlRefCat.current) {
        URL.revokeObjectURL(blobUrlRefCat.current);
        blobUrlRefCat.current = null;
      }
    };
  }, []);

  // Handle escape key to close expanded view
  useEffect(() => {
    const handleEscapeKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && expandedKind) {
        setExpandedKind(null);
      }
    };

    if (expandedKind) {
      document.addEventListener('keydown', handleEscapeKey);
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.removeEventListener('keydown', handleEscapeKey);
      document.body.style.overflow = 'unset';
    };
  }, [expandedKind]);

  // Auto-load heatmap whenever dataset is available (cache handles deduplication)
  useEffect(() => {
    if (effectiveDatasetId) {
      loadHeatmap(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, effectiveDatasetId, effectiveTargetVar, isDark]);

  // Reload heatmap when top features selection changes
  useEffect(() => {
    if (effectiveDatasetId) {
      loadHeatmap(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topFeaturesNumeric, topFeaturesCategorical]);

  // Listen for data scope changes
  useEffect(() => {
    const handleScopeChange = (event: CustomEvent) => {
      const { dataset_id, scope } = event.detail;
      
      console.log('🔄 MulticollinearityAnalysisComponent - Scope changed:', {
        dataset_id,
        scope,
        currentDatasetId: effectiveDatasetId
      });
      
      // Only refresh if it's for the current dataset
      if (dataset_id === effectiveDatasetId) {
        console.log('🔄 Refreshing multicollinearity heatmap for new scope:', scope);
        loadHeatmap(true);
      }
    };

    // Add event listener
    window.addEventListener('datasetScopeChanged', handleScopeChange as EventListener);
    
    // Cleanup
    return () => {
      window.removeEventListener('datasetScopeChanged', handleScopeChange as EventListener);
    };
  }, [effectiveDatasetId]);

  const loadHeatmap = async (forceRefresh: boolean = false) => {
    if (!effectiveDatasetId) return;
    if (isLoadingRef.current && !forceRefresh) {
      console.log('🧪 Multicollinearity skip fetch: already loading');
      return;
    }
    isLoadingRef.current = true;
    try {
      setLoading(true);
      setError(null);
      triedBlobNumericRef.current = false;
      triedBlobCatRef.current = false;
      if (blobUrlRefNumeric.current) {
        URL.revokeObjectURL(blobUrlRefNumeric.current);
        blobUrlRefNumeric.current = null;
      }
      if (blobUrlRefCat.current) {
        URL.revokeObjectURL(blobUrlRefCat.current);
        blobUrlRefCat.current = null;
      }

      if (!forceRefresh) {
        const cached = heatmapCache.get(cacheKey);
        if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
          console.log('🧪 Multicollinearity cache hit for', cacheKey);
          setUri(cached.numeric);
          setCatUri(cached.categorical);
          setLoading(false);
          return;
        }
      }

      const [numOutcome, catOutcome] = await Promise.allSettled([
        multicollinearityService.getHeatmapImage(
          effectiveDatasetId,
          effectiveTargetVar || undefined,
          isDark,
          topFeaturesNumeric
        ),
        multicollinearityService.getCategoricalHeatmapImage(
          effectiveDatasetId,
          effectiveTargetVar || undefined,
          isDark,
          topFeaturesCategorical
        ),
      ]);

      if (numOutcome.status === 'rejected') {
        throw numOutcome.reason;
      }
      const imageUri = numOutcome.value;
      setUri(imageUri);

      let categorical: string | null = null;
      if (catOutcome.status === 'fulfilled') {
        categorical = catOutcome.value;
      } else {
        console.warn('🧪 Categorical heatmap skipped:', catOutcome.reason);
      }
      setCatUri(categorical);

      heatmapCache.set(cacheKey, {
        numeric: imageUri,
        categorical,
        ts: Date.now(),
      });
    } catch (e: any) {
      if (!mountedRef.current) return;
      setError(e?.message || 'Failed to load heatmap');
      setUri(null);
      setCatUri(null);
      console.error('🧪 Multicollinearity load error:', e);
    } finally {
      // Always clear loading even if unmounted to avoid sticky spinner in dev re-mounts
      setLoading(false);
      isLoadingRef.current = false;
    }
  };

  const dataUriToBlobUrl = (dataUri: string): string => {
    const parts = dataUri.split(',');
    const header = parts[0] || '';
    const base64 = parts[1] || '';
    const mimeMatch = header.match(/data:(.*?);base64/);
    const mime = mimeMatch ? mimeMatch[1] : 'image/png';
    const byteChars = atob(base64);
    const byteNumbers = new Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
      byteNumbers[i] = byteChars.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: mime });
    return URL.createObjectURL(blob);
  };

  const handleImageError = () => {
    console.error('🧪 Heatmap image failed to load (data URI). Trying Blob URL fallback...');
    if (triedBlobNumericRef.current || !uri) return;
    try {
      const blobUrl = dataUriToBlobUrl(uri);
      if (blobUrlRefNumeric.current) {
        URL.revokeObjectURL(blobUrlRefNumeric.current);
      }
      blobUrlRefNumeric.current = blobUrl;
      triedBlobNumericRef.current = true;
      setUri(blobUrl);
    } catch (e) {
      console.error('🧪 Blob fallback failed', e);
      setError('Failed to render heatmap image');
    }
  };

  const handleImageErrorCategorical = () => {
    console.error('🧪 Categorical heatmap image failed to load (data URI). Trying Blob URL fallback...');
    if (triedBlobCatRef.current || !catUri) return;
    try {
      const blobUrl = dataUriToBlobUrl(catUri);
      if (blobUrlRefCat.current) {
        URL.revokeObjectURL(blobUrlRefCat.current);
      }
      blobUrlRefCat.current = blobUrl;
      triedBlobCatRef.current = true;
      setCatUri(blobUrl);
    } catch (e) {
      console.error('🧪 Blob fallback failed (categorical)', e);
      setCatUri(null);
    }
  };

  const downloadCorrelationMatrixExcel = async () => {
    if (!effectiveDatasetId) {
      alert('Dataset is required to export.');
      return;
    }
    setIsExcelDownloading(true);
    try {
      const infoRows: ReportCell[][] = [
        ['Field', 'Value'],
        ['Dataset ID', effectiveDatasetId],
        ['Target variable (config)', effectiveTargetVar ?? '—'],
        ['Data scope', dataScope],
        ['Exported (UTC)', new Date().toISOString()],
        ['UI numeric heatmap', uri ? 'Loaded' : 'Not loaded'],
        ['UI categorical heatmap', catUri ? 'Loaded' : 'Not loaded'],
      ];

      let matrixGrid: ReportCell[][] = [['(No matrix data)']];
      if (effectiveTargetVar) {
        try {
          const matrixPayload = await multicollinearityService.getFullCorrelationMatrixData(
            effectiveDatasetId,
            effectiveTargetVar,
            'pearson'
          );
          const cm = matrixPayload.correlation_matrix || {};
          if (Object.keys(cm).length > 0) {
            matrixGrid = correlationDictToSquareGrid(cm);
          } else {
            matrixGrid = [
              ['No numeric correlation matrix returned after preprocessing (no usable numeric columns).'],
            ];
          }
        } catch (apiErr: unknown) {
          console.warn('Correlation matrix export API:', apiErr);
          const msg = apiErr instanceof Error ? apiErr.message : String(apiErr);
          matrixGrid = [['Could not load full numeric matrix from the API.'], [msg]];
        }
      } else {
        matrixGrid = [
          [
            'Configure a target variable for the dataset to request the full numeric correlation matrix from the API.',
          ],
        ];
      }

      const charts: {
        sheetName: string;
        base64Png: string;
        extension?: 'png' | 'jpeg';
        width?: number;
        height?: number;
      }[] = [];

      if (uri) {
        const img = await imageUrlToExcelImage(uri);
        if (img) {
          charts.push({
            sheetName: 'Numeric heatmap',
            base64Png: img.base64,
            extension: img.extension,
            width: 720,
            height: 520,
          });
        }
      }
      if (catUri) {
        const img = await imageUrlToExcelImage(catUri);
        if (img) {
          charts.push({
            sheetName: 'Categorical heatmap',
            base64Png: img.base64,
            extension: img.extension,
            width: 720,
            height: 520,
          });
        }
      }

      const safe = String(effectiveDatasetId).replace(/[^a-zA-Z0-9_-]/g, '_');
      const fname = `Correlation_Matrix_${safe}_${new Date().toISOString().split('T')[0]}.xlsx`;

      await downloadExcelWorkbookWithCharts({
        filename: fname,
        sheets: [
          { name: 'Methodology', rows: correlationMatrixMethodologyAoA() },
          { name: 'Report info', rows: infoRows },
          { name: 'Full matrix', rows: matrixGrid },
        ],
        charts: charts.length ? charts : undefined,
      });
    } catch (e) {
      console.error('Excel export failed:', e);
      alert('Could not build the Excel file.');
    } finally {
      setIsExcelDownloading(false);
    }
  };

  // Only available on step 3
  if (!effectiveDatasetId) {
    return (
      <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg p-4">
        <div className="flex items-center space-x-2">
          <AlertTriangle className="h-5 w-5 text-yellow-600" />
          <span className="text-yellow-800 dark:text-yellow-300 font-medium">Dataset Required</span>
        </div>
        <p className="text-yellow-700 dark:text-yellow-400 text-sm mt-1">Please ensure a dataset is loaded.</p>
      </div>
    );
  }

  // Show loading state when analyzing
  if (loading) {
    return (
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-6 text-center">
        <Loader className="h-8 w-8 text-blue-600 animate-spin mx-auto mb-3" />
        <h3 className="font-medium text-blue-900 dark:text-blue-300 mb-2">Generating Correlation Heatmap</h3>
        <p className="text-blue-700 dark:text-blue-400 text-sm">
          Analyzing correlations between numeric variables and generating heatmap visualization...
        </p>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="space-y-4">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-4 text-center">
          <AlertTriangle className="h-8 w-8 text-red-600 mx-auto mb-3" />
          <h3 className="font-medium text-red-900 dark:text-red-300 mb-2">Analysis Failed</h3>
          <p className="text-red-700 dark:text-red-400 text-sm mb-4">{error}</p>
        </div>
        
        {/* Action Buttons */}
        <div className="mt-1 pt-4 border-t border-gray-200 dark:border-gray-700 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => loadHeatmap(true)}
            className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] transition-colors text-sm"
            title="Retry multicollinearity analysis"
          >
            Retry Analysis
          </button>
          <button
            type="button"
            onClick={() => void downloadCorrelationMatrixExcel()}
            disabled={isExcelDownloading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors text-sm"
            title="Download Excel workbook (.xlsx)"
          >
            {isExcelDownloading ? (
              <Loader className="h-4 w-4 animate-spin shrink-0" />
            ) : (
              <FileDown className="h-4 w-4 shrink-0" />
            )}
            Download Report
          </button>
        </div>
      </div>
    );
  }

  const expandedSrc =
    expandedKind === 'numeric' ? uri : expandedKind === 'categorical' ? catUri : null;
  const expandedOnError =
    expandedKind === 'numeric' ? handleImageError : expandedKind === 'categorical' ? handleImageErrorCategorical : undefined;

  // Show expanded modal (same structure as original)
  if (expandedKind && expandedSrc) {
    return (
      <>
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40"
          onClick={() => setExpandedKind(null)}
        />

        {/* Expanded Heatmap Modal */}
        <div className="fixed inset-4 z-50 overflow-auto">
          <div className="min-h-full flex items-center justify-center p-4">
            <div className="w-full max-w-7xl mx-auto">
              {/* Modal Header */}
              <div className="bg-white dark:bg-gray-800 rounded-t-lg border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center space-x-2">
                  <ImageIcon className="h-5 w-5 text-purple-600" />
                  <span>Correlation Heatmap Result - Expanded View</span>
                </h3>
                <button
                  onClick={() => setExpandedKind(null)}
                  className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  title="Close expanded view"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Expanded Heatmap */}
              <div className="bg-white dark:bg-gray-800 rounded-b-lg p-6">
                <div className="flex justify-center">
                  <img
                    src={expandedSrc}
                    alt="Correlation heatmap - Expanded view"
                    className="max-w-full max-h-[80vh] object-contain rounded"
                    onError={expandedOnError}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </>
    );
  }

  // Show results
  return (
    <div className="space-y-5">
      {uri ? (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium text-gray-900 dark:text-gray-100 flex items-center space-x-2">
              <ImageIcon className="h-5 w-5 text-purple-600" />
              <span>Correlation Heatmap Result- Numerical</span>
            </h4>
            <select
              value={topFeaturesNumeric}
              onChange={(e) => setTopFeaturesNumeric(Number(e.target.value))}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
              <option value={15}>Top 15</option>
              <option value={20}>Top 20</option>
            </select>
          </div>

          <div className="relative bg-gray-50 dark:bg-gray-900/50 rounded-lg p-2">
            {/* Expand/Collapse Button */}
            <button
              onClick={() => setExpandedKind('numeric')}
              className="absolute top-2 right-2 z-10 p-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-white dark:hover:bg-gray-700 hover:shadow-sm rounded-lg transition-colors"
              title="Expand heatmap"
            >
              <Maximize2 className="h-4 w-4" />
            </button>

            <img
              src={uri}
              alt="Correlation heatmap"
              className="max-w-full h-auto rounded"
              onError={handleImageError}
            />
          </div>
        </div>
      ) : (
        <div className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 text-center">
          <p className="text-gray-600 dark:text-gray-400 text-sm">No analysis results available</p>
        </div>
      )}

      {uri && catUri ? (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium text-gray-900 dark:text-gray-100 flex items-center space-x-2">
              <ImageIcon className="h-5 w-5 text-purple-600" />
              <span>Correlation Heatmap Result- Categorical</span>
            </h4>
            <select
              value={topFeaturesCategorical}
              onChange={(e) => setTopFeaturesCategorical(Number(e.target.value))}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
              <option value={15}>Top 15</option>
              <option value={20}>Top 20</option>
            </select>
          </div>

          <div className="relative bg-gray-50 dark:bg-gray-900/50 rounded-lg p-2">
            {/* Expand/Collapse Button */}
            <button
              onClick={() => setExpandedKind('categorical')}
              className="absolute top-2 right-2 z-10 p-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-white dark:hover:bg-gray-700 hover:shadow-sm rounded-lg transition-colors"
              title="Expand heatmap"
            >
              <Maximize2 className="h-4 w-4" />
            </button>

            <img
              src={catUri}
              alt="Correlation heatmap"
              className="max-w-full h-auto rounded"
              onError={handleImageErrorCategorical}
            />
          </div>
        </div>
      ) : null}

      {/* Action Buttons */}
      <div className="mt-1 pt-4 border-t border-gray-200 dark:border-gray-700 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => {
            heatmapCache.delete(cacheKey);
            setUri(null);
            setCatUri(null);
            loadHeatmap(true);
          }}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 transition-colors text-sm"
          title="Force refresh multicollinearity analysis"
        >
          Refresh Analysis
        </button>
        <button
          type="button"
          onClick={() => void downloadCorrelationMatrixExcel()}
          disabled={loading || isExcelDownloading}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors text-sm"
          title="Download Excel workbook (.xlsx)"
        >
          {isExcelDownloading ? (
            <Loader className="h-4 w-4 animate-spin shrink-0" />
          ) : (
            <FileDown className="h-4 w-4 shrink-0" />
          )}
          Download Report
        </button>
      </div>
    </div>
  );
};

export default MulticollinearityAnalysisComponent;


