import React, { useState, useRef, useEffect, memo, Suspense, lazy } from 'react';
import { Pencil, Save, X, Download, RefreshCw, Loader } from 'lucide-react';
import { useDocumentation } from '../contexts/DocumentationContext';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';
import { Pie, Bar } from 'react-chartjs-2';
import CollapsibleSection from './CollapsibleSection';
import VirtualizedTable from './VirtualizedTable';

// Lazy load heavy chart components
const ROCCurveComparison = lazy(() => import('./ModelEvaluation/ROCCurveComparison'));
const PerformanceRadarChart = lazy(() => import('./ModelEvaluation/PerformanceRadarChart'));
const ConfusionMatrixComparison = lazy(() => import('./ModelEvaluation/ConfusionMatrixComparison'));
const SHAPBeeswarmPlotCanvas = lazy(() => import('./ModelEvaluation/SHAPBeeswarmPlotCanvas'));
const SHAPWaterfallPlot = lazy(() => import('./ModelEvaluation/SHAPWaterfallPlot'));
const PDPICEPlotCanvas = lazy(() => import('./ModelEvaluation/PDPICEPlotCanvas'));

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

interface EditableFieldProps {
  value: string;
  onSave: (value: string) => void;
  multiline?: boolean;
  label?: string;
  renderBullets?: boolean;
}

// Memoized Chart Components with forwardRef support for Pie
const MemoizedPie = memo(React.forwardRef<any, any>((props, ref) => <Pie {...props} ref={ref} />));
const MemoizedBar = memo(Bar);

// Memoized wrapper for ROCCurveComparison
const MemoizedROCCurveComparison = memo(({ models, title }: { models: any; title: string }) => (
  <Suspense fallback={<div className="text-center py-8"><Loader className="h-8 w-8 animate-spin mx-auto" /></div>}>
    <ROCCurveComparison models={models} title={title} />
  </Suspense>
));

// Memoized wrapper for PerformanceRadarChart
const MemoizedPerformanceRadarChart = memo(({ models, title }: { models: any; title: string }) => (
  <Suspense fallback={<div className="text-center py-8"><Loader className="h-8 w-8 animate-spin mx-auto" /></div>}>
    <PerformanceRadarChart models={models} title={title} />
  </Suspense>
));

// Memoized wrapper for ConfusionMatrixComparison
const MemoizedConfusionMatrixComparison = memo(({ models, title }: { models: any; title?: string }) => (
  <Suspense fallback={<div className="text-center py-8"><Loader className="h-8 w-8 animate-spin mx-auto" /></div>}>
    <ConfusionMatrixComparison models={models} title={title} />
  </Suspense>
));

const EditableField: React.FC<EditableFieldProps> = ({ value, onSave, multiline = false, renderBullets = false }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);

  const handleSave = () => {
    onSave(editValue);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditValue(value);
    setIsEditing(false);
  };

  // Parse content into intro text and bullet points
  const parseBulletContent = (content: string) => {
    if (!content) return { intro: '', bullets: [] };
    
    const lines = content.split('\n');
    const intro: string[] = [];
    const bullets: string[] = [];
    
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        if (trimmed.startsWith('- ')) {
          bullets.push(trimmed.substring(2)); // Remove "- " prefix
        } else {
          intro.push(trimmed);
        }
      }
    }
    
    return {
      intro: intro.join(' '),
      bullets
    };
  };

  if (isEditing) {
    return (
      <div className="space-y-2">
        {multiline ? (
          <textarea
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="w-full px-3 py-2 border border-blue-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={5}
            autoFocus
          />
        ) : (
          <input
            type="text"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="w-full px-3 py-2 border border-blue-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoFocus
          />
        )}
        <div className="flex items-center space-x-2">
          <button
            onClick={handleSave}
            className="px-3 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center space-x-1 text-sm"
          >
            <Save className="h-3 w-3" />
            <span>Save</span>
          </button>
          <button
            onClick={handleCancel}
            className="px-3 py-1 bg-gray-300 text-gray-700 dark:bg-slate-700 dark:text-gray-100 rounded-lg hover:bg-gray-400 dark:hover:bg-slate-600 flex items-center space-x-1 text-sm"
          >
            <X className="h-3 w-3" />
            <span>Cancel</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="group relative">
      <div className="pr-8">
        {multiline && renderBullets ? (
          (() => {
            const { intro, bullets } = parseBulletContent(value);
            return (
              <div className="text-gray-700 space-y-2">
                {intro && <p className="mb-3">{intro}</p>}
                {bullets.length > 0 && (
                  <ul className="list-disc list-inside space-y-1 ml-4">
                    {bullets.map((bullet, index) => (
                      <li key={index}>{bullet}</li>
                    ))}
                  </ul>
                )}
                {!intro && bullets.length === 0 && <p>No content provided</p>}
              </div>
            );
          })()
        ) : multiline ? (
          <p className="text-gray-700 whitespace-pre-wrap">{value || 'No content provided'}</p>
        ) : (
          <span className="text-gray-700">{value || 'Not provided'}</span>
        )}
      </div>
      <button
        onClick={() => setIsEditing(true)}
        className="absolute top-0 right-0 p-1 text-gray-400 hover:text-blue-600 transition-opacity"
        title="Edit"
      >
        <Pencil className="h-4 w-4" />
      </button>
    </div>
  );
};

interface DocumentationViewerProps {
  onDownload: () => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  isDownloading?: boolean;
}

const DocumentationViewer: React.FC<DocumentationViewerProps> = ({ onDownload, onRefresh, isRefreshing, isDownloading = false }) => {
  const { documentationData, updateModelObjective, updateDataSummary, updateDataOverview, updateTargetDefinition, updateModelOwner, updateModelPerformance, updateSegmentation, updateDataTreatment, updateDataInsights, updateFeatureEngineering, updateModelSelection, updateSamplingPlan, updateModelValidation } = useDocumentation();
  const pieChartRef = useRef<any>(null);
  const pieChartCanvasRef = useRef<HTMLCanvasElement | null>(null);
  
  // Get used features for filtering from section 7.1.1 Final Set of Variables
  const usedFeatures = React.useMemo(() => {
    try {
      const variableAnalysis = documentationData?.modelDesign?.modelSelection?.finalVariables?.variableAnalysis || [];
      return variableAnalysis.map(stat => (stat?.variable || '').trim()).filter(Boolean);
    } catch (error) {
      console.warn('Error extracting used features from modelSelection:', error);
      return [];
    }
  }, [documentationData?.modelDesign?.modelSelection?.finalVariables?.variableAnalysis]);
  
  // Fallback to modelPerformance if modelSelection is not available
  const usedFeaturesFallback = React.useMemo(() => {
    try {
      return (documentationData?.modelPerformance?.features?.usedFeatures || []).map(f => (f || '').trim()).filter(Boolean);
    } catch (error) {
      console.warn('Error extracting used features from modelPerformance:', error);
      return [];
    }
  }, [documentationData?.modelPerformance?.features?.usedFeatures]);
  
  const finalUsedFeatures = usedFeatures.length > 0 ? usedFeatures : usedFeaturesFallback;
  
  // Helper function to filter rows based on rowsToShow value and usedFeatures
  const filterDataInsightsRows = <T extends { Variable?: string; 'Variable Name'?: string }>(
    rows: T[],
    rowsToShow: number | string | undefined
  ): T[] => {
    if (!rows || rows.length === 0) return [];
    
    // Normalize rowsToShow - handle string numbers from select
    let normalizedRowsToShow: number | string | undefined = rowsToShow;
    if (typeof rowsToShow === 'string' && rowsToShow !== 'all' && rowsToShow !== 'used_features') {
      const parsed = parseInt(rowsToShow, 10);
      if (!isNaN(parsed)) {
        normalizedRowsToShow = parsed;
      }
    }
    
    // Handle different filter options
    if (normalizedRowsToShow === 'used_features') {
      // Filter to only show variables that are in usedFeatures
      return rows.filter(row => {
        const varName = (row.Variable || row['Variable Name'] || '').trim();
        return finalUsedFeatures.some(uf => uf === varName);
      });
    } else if (normalizedRowsToShow === 'all') {
      // Show all rows without filtering
      return rows;
    } else if (typeof normalizedRowsToShow === 'number') {
      // Show first N rows (all rows, not filtered by used_features)
      return rows.slice(0, normalizedRowsToShow);
    } else {
      // Default: if rowsToShow is undefined, default to "used_features"
      return rows.filter(row => {
        const varName = (row.Variable || row['Variable Name'] || '').trim();
        return finalUsedFeatures.some(uf => uf === varName);
      });
    }
  };

  // Static scaffolding for Variable Transformation & Feature Selection placeholders.
  const modelDevelopmentPlaceholders: Array<{
    id: string;
    title: string;
    description: string;
    children: Array<{ id: string; title: string; body: string }>;
  }> = [
    // Hidden sections 3.1 and 3.2 per user request
    // {
    //   id: '3.1',
    //   title: 'Variable Transformation',
    //   description: 'Summaries about binning, scaling, missing value treatments, and business-ready feature transformations will surface here once Model Development is completed.',
    //   children: [],
    // },
    // {
    //   id: '3.2',
    //   title: 'Feature Selection',
    //   description: 'Key checkpoints in the feature selection pipeline. Each item captures rationale and decisions for audit readiness.',
    //   children: [
    //     {
    //       id: '3.2.1',
    //       title: 'Zero variance',
    //       body: 'Track the list of columns dropped because of zero variance checks. Placeholder text until feature selection runs.',
    //     },
    //     {
    //       id: '3.2.2',
    //       title: 'Correlation greater than 99.9%',
    //       body: 'Capture highly correlated feature pairs and the retained driver variable. Placeholder block mirrors Model Objective fonts.',
    //     },
    //     {
    //       id: '3.2.3',
    //       title: 'Initial CSI Check',
    //       body: 'Explain stability checks (CSI/PSI) performed on shortlisted attributes. Use this area to note date ranges and reference datasets.',
    //     },
    //     {
    //       id: '3.2.4',
    //       title: 'Final Candidate Variables',
    //       body: 'Document the surviving candidate inputs with a short justification. Placeholder stays until pipeline emits structured output.',
    //     },
    //   ],
    // },
  ];

  const modelSelectionData = documentationData?.modelDesign?.modelSelection || {
    hyperparameters: { summaryList: [] },
    finalVariables: { categories: [] }
  };
  const hasHyperparameters = (modelSelectionData?.hyperparameters?.summaryList?.length || 0) > 0;
  const hasVariableCategories = (modelSelectionData?.finalVariables?.categories?.length || 0) > 0;

  // Capture pie chart as image when it's rendered
  useEffect(() => {
    const capturePieChart = async () => {
      try {
        const categories = documentationData?.modelDesign?.dataOverview?.variableCategorization?.categories || {};
        if (Object.keys(categories).length > 0) {
          // Try multiple ways to access the canvas
          let canvas: HTMLCanvasElement | null = null;
          
          // Method 1: Use canvas ref if available
          if (pieChartCanvasRef.current) {
            canvas = pieChartCanvasRef.current;
          }
          // Method 2: Try to get from chart ref
          else if (pieChartRef.current) {
            // Method 2a: Direct canvas property
            if (pieChartRef.current.canvas) {
              canvas = pieChartRef.current.canvas;
            }
            // Method 2b: Get chart instance and access canvas
            else if (pieChartRef.current.getChart) {
              const chart = pieChartRef.current.getChart();
              canvas = chart?.canvas || null;
            }
            // Method 2c: Access via chartInstance
            else if (pieChartRef.current.chartInstance) {
              canvas = pieChartRef.current.chartInstance.canvas;
            }
            // Method 2d: Find canvas element in the ref's container
            else if (pieChartRef.current.container) {
              canvas = pieChartRef.current.container.querySelector('canvas');
            }
            // Method 2e: Try to find canvas in the DOM near the ref
            else {
              // Find the canvas element by searching for it near where the chart should be
              const chartContainer = document.querySelector('[data-pie-chart-container]');
              if (chartContainer) {
                canvas = chartContainer.querySelector('canvas');
              }
            }
          }
          
          if (canvas) {
            // Check if canvas has valid dimensions
            if (canvas.width === 0 || canvas.height === 0) {
              console.warn('📊 Pie chart canvas has zero dimensions:', canvas.width, 'x', canvas.height);
              return;
            }
            
            // Force chart to update if we have the chart instance
            if (pieChartRef.current) {
              try {
                const chart = pieChartRef.current.getChart ? pieChartRef.current.getChart() : pieChartRef.current;
                if (chart && chart.update) {
                  chart.update('none'); // Force update without animation
                  // Wait a bit for the update to complete
                  await new Promise(resolve => setTimeout(resolve, 100));
                }
              } catch (e) {
                console.warn('Failed to force chart update:', e);
              }
            }
            
            // Get image data with better quality
            const imageData = canvas.toDataURL('image/png', 1.0);
            
            // Validate that image data is not empty and has reasonable length
            if (imageData && imageData !== 'data:,' && imageData.length > 100) {
              // Additional validation: check if image is not just white/blank
              // by checking if the base64 data has meaningful content
              const base64Data = imageData.split(',')[1];
              if (base64Data && base64Data.length > 1000) {
                // Store in context for .docx generation
                updateDataOverview({
                  variableCategorization: {
                    ...(documentationData?.modelDesign?.dataOverview?.variableCategorization || {}),
                    imageData: imageData,
                  }
                });
                console.log('📊 Pie chart captured as image for export', `Size: ${canvas.width}x${canvas.height}, Data length: ${imageData.length}`);
              } else {
                console.warn('📊 Pie chart image data too short, likely blank:', base64Data?.length || 0);
              }
            } else {
              console.warn('📊 Pie chart canvas returned empty or invalid image data, length:', imageData?.length || 0);
            }
          } else {
            console.warn('📊 Pie chart canvas not found. Ref:', pieChartRef.current, 'Canvas ref:', pieChartCanvasRef.current);
          }
        }
      } catch (error) {
        console.error('Failed to capture pie chart:', error);
      }
    };

    // Capture after multiple attempts to ensure chart is fully rendered
    const timer1 = setTimeout(capturePieChart, 2000);
    const timer2 = setTimeout(capturePieChart, 3000);
    const timer3 = setTimeout(capturePieChart, 4000);
    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
    };
  }, [documentationData?.modelDesign?.dataOverview?.variableCategorization?.categories, updateDataOverview]);

  // Debug logging
  console.log('📄 DocumentationViewer - Current Data:');
  console.log('  - Model Objective Description:', documentationData.objectives.modelObjective.description);
  console.log('  - Model Objective Problem Statement:', documentationData.objectives.modelObjective.problemStatement);
  console.log('  - Data Summary:', documentationData.objectives.dataSummary.content);

  // Helper functions to check if sections have data
  const hasObjectiveData = () => {
    const desc = documentationData.objectives.modelObjective.description;
    const prob = documentationData.objectives.modelObjective.problemStatement;
    const summary = documentationData.objectives.dataSummary.content;
    return !!(desc || prob || (summary && summary !== 'Not provided'));
  };

  const hasModelDesignData = () => {
    const dataOverview = documentationData.modelDesign.dataOverview;
    const datasetStats = dataOverview.datasetStats;
    const edaReport = dataOverview.edaReport?.table || [];
    const dataQuality = dataOverview.dataQuality;
    const categories = dataOverview.variableCategorization?.categories || {};
    const targetDefinition = documentationData.modelDesign.targetDefinition;
    const samplingPlan = documentationData.modelDesign.samplingPlan;
    const modelValidation = documentationData.modelDesign.modelValidation;
    return !!(
      datasetStats ||
      (edaReport.length > 0) ||
      dataQuality ||
      (Object.keys(categories).length > 0) ||
      targetDefinition ||
      samplingPlan ||
      modelValidation
    );
  };

  const hasDataTreatmentData = () => {
    const dataTreatment = documentationData.modelDesign.dataTreatment;
    const writeup = dataTreatment.implementedQualityChanges?.writeup?.content;
    const planTable = dataTreatment.qualityCheckPlan?.table || [];
    const columnStats = dataTreatment.implementedQualityChanges?.columnStats || [];
    return !!(writeup || planTable.length > 0 || columnStats.length > 0);
  };

  const hasDataInsightsData = () => {
    const dataInsights = documentationData.dataInsights;
    if (!dataInsights) return false;
    const bivariate = dataInsights.bivariateAnalysis;
    const iv = dataInsights.ivAnalysis;
    const correlation = dataInsights.correlationAnalysis;
    const vif = dataInsights.vifAnalysis;
    return !!(
      (bivariate && (bivariate.insights || bivariate.edaReport)) ||
      (iv && (iv.insights || iv.edaReport)) ||
      (correlation && correlation.edaReport) ||
      (vif && (vif.insights || vif.edaReport))
    );
  };

  const hasSegmentationData = () => {
    const segmentation = documentationData.modelDesign.segmentation;
    if (!segmentation || !segmentation.hasSegmentation) return false;
    return !!(
      segmentation.understanding ||
      segmentation.variablesUsed ||
      segmentation.method ||
      segmentation.segments ||
      segmentation.segmentSizesChart ||
      segmentation.segmentProportionsChart ||
      segmentation.ivVisualizationCharts
    );
  };

  const hasModelPerformanceData = () => {
    const modelPerformance = documentationData.modelPerformance;
    const features = modelPerformance.features;
    const topFeatures = features.topFeatures || [];
    const usedFeatures = features.usedFeatures || [];
    return !!(
      topFeatures.length > 0 ||
      usedFeatures.length > 0 ||
      modelPerformance.rocCurves ||
      modelPerformance.radarCharts ||
      modelPerformance.monotonicity
    );
  };

  // Removed unused helper functions - they're not needed with collapsible sections

  // Determine available data insights sections and their order
  const availableSections: Array<{key: string, name: string}> = [];
  if (documentationData.dataInsights?.bivariateAnalysis) {
    availableSections.push({ key: 'bivariateAnalysis', name: 'Bivariate Analysis' });
  }
  if (documentationData.dataInsights?.ivAnalysis) {
    availableSections.push({ key: 'ivAnalysis', name: 'Information Value (IV)' });
  }
  if (documentationData.dataInsights?.correlationAnalysis) {
    availableSections.push({ key: 'correlationAnalysis', name: 'Correlation Matrix' });
  }
  if (documentationData.dataInsights?.correlationAnalysisNumeric) {
    availableSections.push({ key: 'correlationAnalysisNumeric', name: 'Correlation Analysis' });
  }
  if (documentationData.dataInsights?.vifAnalysis) {
    availableSections.push({ key: 'vifAnalysis', name: 'Variable Inflation Factor (VIF)' });
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-8 space-y-8 model-documentation">
      {/* Header */}
      <div className="border-b border-gray-300 pb-4 flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Model Documentation</h2>
          <p className="text-gray-600 mt-1">
            Generated on {new Date(documentationData.meta.lastUpdated).toLocaleString()}
          </p>
        </div>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={isRefreshing}
            className="inline-flex items-center px-4 py-2 border border-blue-200 rounded-lg text-sm font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isRefreshing ? (
              <>
                <Loader className="h-4 w-4 mr-2 animate-spin" />
                <span>Refreshing...</span>
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4 mr-2" />
                <span>Refresh</span>
              </>
            )}
          </button>
        )}
      </div>

      {/* OBJECTIVE Section */}
      <CollapsibleSection sectionNumber={1} sectionTitle="OBJECTIVE" defaultExpanded={true}>
        {() => (
          <>
            {!hasObjectiveData() ? (
              <div className="pl-6">
                <p className="text-gray-700">You skipped to the documentation, upload the Data first</p>
              </div>
            ) : (
              <>
                {/* Model Objective Sub-section */}
                <div className="pl-6 space-y-3">
                  <h4 className="text-lg font-bold text-gray-800">Model Objective</h4>
                  
                  <div className="space-y-2">
                    {documentationData.objectives.modelObjective.generatedObjective ? (
                      <EditableField
                        value={documentationData.objectives.modelObjective.generatedObjective}
                        onSave={(value) => updateModelObjective({ generatedObjective: value })}
                        multiline
                      />
                    ) : (
                      <p className="text-gray-500 italic">Model objective will be generated after data summary and target definition are available.</p>
                    )}
                    
                    {documentationData.objectives.modelObjective.lastGenerated && (
                      <p className="text-xs text-gray-500 italic">
                        Generated on: {new Date(documentationData.objectives.modelObjective.lastGenerated).toLocaleString()}
                      </p>
                    )}
                  </div>
                </div>

                {/* Data Summary Sub-section */}
                <div className="pl-6 space-y-3 pt-4">
                  <h4 className="text-lg font-bold text-gray-800">Data Summary</h4>
                  
                  <div className="space-y-2">
                    <EditableField
                      value={documentationData.objectives.dataSummary.content}
                      onSave={(value) => updateDataSummary({ content: value })}
                      multiline
                    />
                  </div>

                  {documentationData.objectives.dataSummary.metadata.lastGenerated && (
                    <p className="text-xs text-gray-500 italic">
                      Generated on: {new Date(documentationData.objectives.dataSummary.metadata.lastGenerated).toLocaleString()}
                    </p>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </CollapsibleSection>

      {/* MODEL DESIGN Section */}
      <CollapsibleSection sectionNumber={2} sectionTitle="MODEL DESIGN" defaultExpanded={false}>
        {() => (
          <>
            {!hasModelDesignData() ? (
              <div className="pl-6">
                <p className="text-gray-700">You skipped to the documentation, upload the Data first</p>
              </div>
            ) : (
              <>
                {/* 2.1 DATA OVERVIEW Sub-section */}
                <div className="pl-6 space-y-4">
          <h4 className="text-lg font-bold text-gray-800">2.1 Data Overview</h4>
          
          {/* Dataset Statistics */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-700">Dataset Information:</p>
            <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Total Rows:</span>
                  <p className="font-semibold text-gray-900">
                    {documentationData.modelDesign.dataOverview.datasetStats.totalRows.toLocaleString()}
                  </p>
                </div>
                <div>
                  <span className="text-gray-600">Total Columns:</span>
                  <p className="font-semibold text-gray-900">
                    {documentationData.modelDesign.dataOverview.datasetStats.totalColumns}
                  </p>
                </div>
                <div>
                  <span className="text-gray-600">Numerical:</span>
                  <p className="font-semibold text-gray-900">
                    {documentationData.modelDesign.dataOverview.datasetStats.numericalColumns}
                  </p>
                </div>
                <div>
                  <span className="text-gray-600">Categorical:</span>
                  <p className="font-semibold text-gray-900">
                    {documentationData.modelDesign.dataOverview.datasetStats.categoricalColumns}
                  </p>
                </div>
                <div>
                  <span className="text-gray-600">Date:</span>
                  <p className="font-semibold text-gray-900">
                    {documentationData.modelDesign.dataOverview.datasetStats.dateColumns}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* EDA Report - Virtualized for performance */}
          {documentationData.modelDesign.dataOverview.edaReport && documentationData.modelDesign.dataOverview.edaReport.table.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-gray-700">EDA Report:</p>
                {/* Rows filter */}
                <div className="flex items-center space-x-2">
                  <label htmlFor="edaReportRows" className="text-sm text-gray-600">Show</label>
                  <input
                    id="edaReportRows"
                    type="number"
                    min="1"
                    max={documentationData.modelDesign.dataOverview.edaReport.table.length}
                    value={documentationData.modelDesign.dataOverview.edaReport.rowsToShow}
                    onChange={(e) => {
                      const value = parseInt(e.target.value);
                      if (!isNaN(value) && value > 0) {
                        updateDataOverview({
                          edaReport: {
                            ...documentationData.modelDesign.dataOverview.edaReport!,
                            rowsToShow: value,
                          },
                        });
                      }
                    }}
                    className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                  />
                  <span className="text-sm text-gray-600">rows</span>
                </div>
              </div>
              {(() => {
                const edaData = documentationData.modelDesign.dataOverview.edaReport.table.slice(0, documentationData.modelDesign.dataOverview.edaReport.rowsToShow);
                const columns: Array<{ key: string; label: string; align?: 'left' | 'right' | 'center'; render?: (val: any) => any }> = [
                  { key: 'Column', label: 'Column', align: 'left' },
                  { key: 'Data Types', label: 'Data Types', align: 'left' },
                  { key: 'Unique', label: 'Unique', align: 'right', render: (val: number) => val.toLocaleString() },
                  { key: 'Missing', label: 'Missing', align: 'right', render: (val: number) => val.toLocaleString() },
                  { key: 'Mean', label: 'Mean', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                  { key: 'Median', label: 'Median', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                  { key: 'Mode', label: 'Mode', align: 'left' },
                  { key: 'Std', label: 'Std', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                  { key: 'Var', label: 'Var', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                  { key: 'Min', label: 'Min', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                  { key: 'p5%', label: 'p5%', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                  { key: 'p25%', label: 'p25%', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                  { key: 'p50%', label: 'p50%', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                  { key: 'p75%', label: 'p75%', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                  { key: 'p95%', label: 'p95%', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                  { key: 'p99%', label: 'p99%', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                  { key: 'Max', label: 'Max', align: 'right', render: (val: any) => typeof val === 'number' ? val.toFixed(2) : val || '' },
                ];
                
                // Use virtualized table for large datasets, regular table for small ones
                if (edaData.length > 50) {
                  return <VirtualizedTable columns={columns} data={edaData as any[]} height={400} rowHeight={40} />;
                } else {
                  // Fallback to regular table for smaller datasets
                  return (
                    <div className="overflow-x-auto border border-gray-300 rounded-lg">
                      <table className="min-w-full border-collapse">
                        <thead className="bg-gray-100">
                          <tr>
                            {columns.map(col => {
                              let alignClass = 'text-left';
                              if (col.align === 'right') {
                                alignClass = 'text-right';
                              } else if (col.align === 'center') {
                                alignClass = 'text-center';
                              }
                              return (
                                <th key={col.key} className={`px-4 py-2 border-b border-gray-300 font-semibold text-gray-700 ${alignClass}`}>
                                  {col.label}
                                </th>
                              );
                            })}
                          </tr>
                        </thead>
                        <tbody>
                          {edaData.map((row: any, index) => (
                            <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                              {columns.map(col => {
                                const value = (row as Record<string, any>)[col.key];
                                const content = col.render ? col.render(value) : value;
                                let alignClass = 'text-left';
                                if (col.align === 'right') {
                                  alignClass = 'text-right';
                                } else if (col.align === 'center') {
                                  alignClass = 'text-center';
                                }
                                return (
                                  <td key={col.key} className={`px-4 py-2 border-b border-gray-200 text-gray-900 ${alignClass}`}>
                                    {content}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  );
                }
              })()}
            </div>
          )}

          {/* Data Quality Assessment */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-700">Data Quality Assessment:</p>
            <EditableField
              value={documentationData.modelDesign.dataOverview.dataQuality.summary}
              onSave={(value) => updateDataOverview({
                dataQuality: {
                  ...documentationData.modelDesign.dataOverview.dataQuality,
                  summary: value,
                }
              })}
              multiline
              renderBullets
            />
            
            {documentationData.modelDesign.dataOverview.dataQuality.lastGenerated && (
              <p className="text-xs text-gray-500 italic">
                Generated on: {new Date(documentationData.modelDesign.dataOverview.dataQuality.lastGenerated).toLocaleString()}
              </p>
            )}
          </div>

          {/* Variable Categorization Distribution */}
          {Object.keys(documentationData.modelDesign.dataOverview.variableCategorization.categories).length > 0 ? (
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-700">Variable Categorization Distribution:</p>
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Pie Chart */}
                  <div className="flex justify-center items-center" data-pie-chart-container>
                    <div className="w-64 h-64">
                      <MemoizedPie
                        ref={(chartInstance: any) => {
                          pieChartRef.current = chartInstance;
                          // Also try to get the canvas from the chart instance
                          if (chartInstance) {
                            try {
                              const chart = chartInstance.getChart ? chartInstance.getChart() : chartInstance;
                              if (chart && chart.canvas) {
                                pieChartCanvasRef.current = chart.canvas;
                                // Force chart to update and render
                                if (chart.update) {
                                  chart.update('none'); // Update without animation
                                }
                              }
                            } catch (e) {
                              // Ignore errors
                            }
                          }
                        }}
                        data={{
                          labels: Object.keys(documentationData.modelDesign.dataOverview.variableCategorization.categories),
                          datasets: [{
                            data: Object.values(documentationData.modelDesign.dataOverview.variableCategorization.categories),
                            backgroundColor: Object.keys(documentationData.modelDesign.dataOverview.variableCategorization.categories).map(
                              cat => documentationData.modelDesign.dataOverview.variableCategorization.colors[cat] || '#999'
                            ),
                          }]
                        }}
                        options={{
                          responsive: true,
                          maintainAspectRatio: true,
                          plugins: {
                            legend: {
                              display: false,
                            },
                          },
                          animation: {
                            onComplete: () => {
                              // Capture canvas reference after animation completes
                              setTimeout(() => {
                                if (pieChartRef.current) {
                                  try {
                                    const chart = pieChartRef.current.getChart ? pieChartRef.current.getChart() : pieChartRef.current;
                                    if (chart && chart.canvas) {
                                      const canvas = chart.canvas;
                                      pieChartCanvasRef.current = canvas;
                                      
                                      // Wait a bit more to ensure rendering is complete
                                      setTimeout(() => {
                                        if (canvas.width > 0 && canvas.height > 0) {
                                          const imageData = canvas.toDataURL('image/png', 1.0);
                                          if (imageData && imageData !== 'data:,' && imageData.length > 100) {
                                            const base64Data = imageData.split(',')[1];
                                            if (base64Data && base64Data.length > 1000) {
                                              updateDataOverview({
                                                variableCategorization: {
                                                  ...(documentationData?.modelDesign?.dataOverview?.variableCategorization || {}),
                                                  imageData: imageData,
                                                }
                                              });
                                              console.log('📊 Pie chart captured after animation complete', `Size: ${canvas.width}x${canvas.height}`);
                                            }
                                          }
                                        }
                                      }, 200);
                                    }
                                  } catch (e) {
                                    console.warn('Failed to capture canvas in onComplete:', e);
                                  }
                                }
                              }, 100);
                            },
                          },
                        }}
                      />
                    </div>
                  </div>
                  
                  {/* Category Breakdown Legend */}
                  <div className="space-y-2">
                    {Object.entries(documentationData.modelDesign.dataOverview.variableCategorization.categories).map(([category, count]) => {
                      const total = Object.values(documentationData.modelDesign.dataOverview.variableCategorization.categories).reduce((a, b) => a + b, 0);
                      const percentage = ((count as number / total) * 100).toFixed(1);
                      const color = documentationData.modelDesign.dataOverview.variableCategorization.colors[category] || '#999';
                      
                      return (
                        <div key={category} className="flex items-center space-x-2">
                          <div 
                            className="w-4 h-4 rounded" 
                            style={{ backgroundColor: color }}
                          />
                          <span className="text-sm text-gray-700">
                            <span className="font-medium">{category}:</span> {count} variables ({percentage}%)
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-700">Variable Categorization Distribution:</p>
              <div className="bg-yellow-50 p-4 rounded-lg border border-yellow-200">
                <p className="text-sm text-yellow-800">
                  ℹ️ Variable categorization not available. Generate the Knowledge Graph in Step 1 (View Dataset → Overview) to see variable categories.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* 2.2 TARGET DEFINITION Sub-section */}
        <div className="pl-6 space-y-4 pt-4">
          <h4 className="text-lg font-bold text-gray-800">2.2 Target Definition</h4>
          
          {/* Target Variable Name */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-700">Target Variable Name:</p>
            <p className="text-gray-900 font-semibold">
              {documentationData.modelDesign.targetDefinition.targetVariableName || 'Not configured'}
            </p>
          </div>

          {/* Definition */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-700">Definition:</p>
            <EditableField
              value={documentationData.modelDesign.targetDefinition.definition}
              onSave={(value) => updateTargetDefinition({ definition: value })}
              multiline
            />
            {documentationData.modelDesign.targetDefinition.lastGenerated && (
              <p className="text-xs text-gray-500 italic">
                Generated on: {new Date(documentationData.modelDesign.targetDefinition.lastGenerated).toLocaleString()}
              </p>
            )}
          </div>

          {/* Event Rate */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-700">Event Rate:</p>
            <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
              <p className="text-gray-900">
                <span className="font-semibold text-lg">
                  {documentationData.modelDesign.targetDefinition.eventRate.eventCount.toLocaleString()}
                </span>
                <span className="text-gray-600"> / </span>
                <span className="font-semibold text-lg">
                  {documentationData.modelDesign.targetDefinition.eventRate.totalCount.toLocaleString()}
                </span>
                <span className="ml-3 text-blue-600 font-semibold">
                  ({documentationData.modelDesign.targetDefinition.eventRate.percentage.toFixed(2)}%)
                </span>
              </p>
            </div>
          </div>
        </div>

        {/* 2.3 SAMPLING PLAN Sub-section */}
        <div className="pl-6 space-y-4 pt-4">
          <h4 className="text-lg font-bold text-gray-800">2.3 Sampling Plan</h4>
          
          {/* Sampling Plan Writeup */}
          {documentationData.modelDesign.samplingPlan.writeup && (
            <div className="space-y-2">
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <EditableField
                  value={documentationData.modelDesign.samplingPlan.writeup}
                  onSave={(newValue) => {
                    updateSamplingPlan({
                      writeup: newValue,
                    });
                  }}
                  multiline={true}
                />
              </div>
            </div>
          )}
          
          {/* Sampling Table */}
          <div className="space-y-2">
            <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b-2 border-gray-300">
                    <th className="px-4 py-2 text-left font-semibold text-gray-700">Sample</th>
                    <th className="px-4 py-2 text-right font-semibold text-gray-700">Total</th>
                    <th className="px-4 py-2 text-right font-semibold text-gray-700">Event</th>
                    <th className="px-4 py-2 text-right font-semibold text-gray-700">Event Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {/* Train Row */}
                  <tr className="border-b border-gray-200">
                    <td className="px-4 py-2 font-medium text-gray-900">Train</td>
                    <td className="px-4 py-2 text-right text-gray-900">
                      {documentationData.modelDesign.samplingPlan.train.total.toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-900">
                      {documentationData.modelDesign.samplingPlan.train.eventCount.toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-right text-blue-600 font-semibold">
                      {documentationData.modelDesign.samplingPlan.train.eventRate.toFixed(2)}%
                    </td>
                  </tr>
                  
                  {/* Hold Row (only if split exists) */}
                  {documentationData.modelDesign.samplingPlan.hasSplit && (
                    <tr className="border-b border-gray-200">
                      <td className="px-4 py-2 font-medium text-gray-900">Hold</td>
                      <td className="px-4 py-2 text-right text-gray-900">
                        {documentationData.modelDesign.samplingPlan.hold.total.toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-right text-gray-900">
                        {documentationData.modelDesign.samplingPlan.hold.eventCount.toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-right text-blue-600 font-semibold">
                        {documentationData.modelDesign.samplingPlan.hold.eventRate.toFixed(2)}%
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Sampling Identifier */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-700">Sampling Identifier:</p>
            <p className="text-gray-900">
              {documentationData.modelDesign.samplingPlan.samplingIdentifier || 'No Variable selected by user'}
            </p>
          </div>
        </div>

        {/* 2.4 Model Validation */}
        <div className="space-y-4">
          <h4 className="text-lg font-bold text-gray-800">2.4 Model Validation</h4>
          
          {!documentationData.modelDesign.modelValidation.hasHoldDataset ? (
            <p className="text-gray-700 italic">No Hold dataset was available during Model Training</p>
          ) : (
            <div className="space-y-4">
              {/* Best Performing Model */}
              <div>
                <p className="text-gray-900 font-semibold">
                  Best Performing Model: <span className="text-blue-600">{documentationData.modelDesign.modelValidation.bestModel.modelName}</span>
                </p>
              </div>
              
              {/* Model Validation Writeup */}
              {documentationData.modelDesign.modelValidation.writeup && (
                <div className="space-y-2">
                  <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                    <EditableField
                      value={documentationData.modelDesign.modelValidation.writeup}
                      onSave={(newValue) => {
                        updateModelValidation({
                          writeup: newValue,
                        });
                      }}
                      multiline={true}
                    />
                  </div>
                </div>
              )}
              
              {/* Metrics Table */}
              <div>
                <p className="text-gray-900 font-semibold mb-2">On Hold Dataset</p>
                <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b-2 border-gray-300">
                        <th className="px-4 py-2 text-left font-semibold text-gray-700">Accuracy</th>
                        <th className="px-4 py-2 text-left font-semibold text-gray-700">Precision</th>
                        <th className="px-4 py-2 text-left font-semibold text-gray-700">Recall</th>
                        <th className="px-4 py-2 text-left font-semibold text-gray-700">F1 Score</th>
                        <th className="px-4 py-2 text-left font-semibold text-gray-700">AUC-ROC</th>
                        <th className="px-4 py-2 text-left font-semibold text-gray-700">AUC-PR</th>
                        <th className="px-4 py-2 text-left font-semibold text-gray-700">Log Loss</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="px-4 py-2 text-gray-900 font-medium">
                          {(documentationData.modelDesign.modelValidation.bestModel.metrics.accuracy * 100).toFixed(2)}%
                        </td>
                        <td className="px-4 py-2 text-gray-900 font-medium">
                          {documentationData.modelDesign.modelValidation.bestModel.metrics.precision.toFixed(4)}
                        </td>
                        <td className="px-4 py-2 text-gray-900 font-medium">
                          {documentationData.modelDesign.modelValidation.bestModel.metrics.recall.toFixed(4)}
                        </td>
                        <td className="px-4 py-2 text-gray-900 font-medium">
                          {documentationData.modelDesign.modelValidation.bestModel.metrics.f1Score.toFixed(4)}
                        </td>
                        <td className="px-4 py-2 text-gray-900 font-medium">
                          {documentationData.modelDesign.modelValidation.bestModel.metrics.aucRoc.toFixed(4)}
                        </td>
                        <td className="px-4 py-2 text-gray-900 font-medium">
                          {documentationData.modelDesign.modelValidation.bestModel.metrics.aucPr.toFixed(4)}
                        </td>
                        <td className="px-4 py-2 text-gray-900 font-medium">
                          {documentationData.modelDesign.modelValidation.bestModel.metrics.logLoss.toFixed(4)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
              </>
            )}
          </>
        )}
      </CollapsibleSection>

      {/* 3. DATA TREATMENT Section */}
      <CollapsibleSection sectionNumber={3} sectionTitle="DATA TREATMENT" defaultExpanded={false}>
        {() => (
          <>

        {!hasDataTreatmentData() ? (
          <div className="pl-6">
            <p className="text-gray-700">You didn't clean your data! Go to Data Treatment page and pre-process the data.</p>
          </div>
        ) : (
          <div className="pl-6 space-y-6">
          {/* Writeup - moved before 3.1 Quality Check Plan */}
          {documentationData.modelDesign.dataTreatment.implementedQualityChanges.writeup?.content && (
            <div className="space-y-2">
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <EditableField
                  value={documentationData.modelDesign.dataTreatment.implementedQualityChanges.writeup.content}
                  onSave={(newValue) => {
                    updateDataTreatment({
                      implementedQualityChanges: {
                        ...documentationData.modelDesign.dataTreatment.implementedQualityChanges,
                        writeup: {
                          content: newValue,
                          lastGenerated: documentationData.modelDesign.dataTreatment.implementedQualityChanges.writeup?.lastGenerated || null,
                        },
                      },
                    });
                  }}
                  multiline={true}
                />
              </div>
              {documentationData.modelDesign.dataTreatment.implementedQualityChanges.writeup.lastGenerated && (
                <p className="text-xs text-gray-500 italic">
                  Generated on: {new Date(documentationData.modelDesign.dataTreatment.implementedQualityChanges.writeup.lastGenerated).toLocaleString()}
                </p>
              )}
            </div>
          )}

          {/* 3.1 Quality Check Plan */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-lg font-bold text-gray-800">3.1 Quality Check Plan</h4>
              {/* Rows filter */}
              <div className="flex items-center space-x-2">
                <label htmlFor="qualityCheckPlanRows" className="text-sm text-gray-600">Show</label>
                <input
                  id="qualityCheckPlanRows"
                  type="number"
                  min="1"
                  max={documentationData.modelDesign.dataTreatment.qualityCheckPlan.table.length}
                  value={documentationData.modelDesign.dataTreatment.qualityCheckPlan.rowsToShow}
                  onChange={(e) => {
                    const value = parseInt(e.target.value);
                    if (!isNaN(value) && value > 0) {
                      updateDataTreatment({
                        qualityCheckPlan: {
                          ...documentationData.modelDesign.dataTreatment.qualityCheckPlan,
                          rowsToShow: value,
                        },
                      });
                    }
                  }}
                  className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                />
                <span className="text-sm text-gray-600">rows</span>
              </div>
            </div>

            {documentationData.modelDesign.dataTreatment.qualityCheckPlan.table.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full border border-gray-300">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Issue</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Variable</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Observation</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Treatment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documentationData.modelDesign.dataTreatment.qualityCheckPlan.table
                      .slice(0, documentationData.modelDesign.dataTreatment.qualityCheckPlan.rowsToShow)
                      .map((row, index) => (
                        <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{row.Issue}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{row.Variable}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-700">{row.Observation}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-700">{row.Treatment}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-gray-500 italic">No quality check plan data available</p>
            )}
          </div>

          {/* 3.2 Implemented Quality Changes */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-lg font-bold text-gray-800">3.2 Implemented Quality Changes</h4>
              {/* Rows filter */}
              <div className="flex items-center space-x-2">
                <label htmlFor="columnStatsRows" className="text-sm text-gray-600">Show</label>
                <input
                  id="columnStatsRows"
                  type="number"
                  min="1"
                  max={documentationData.modelDesign.dataTreatment.implementedQualityChanges.columnStats.length}
                  value={documentationData.modelDesign.dataTreatment.implementedQualityChanges.rowsToShow}
                  onChange={(e) => {
                    const value = parseInt(e.target.value);
                    if (!isNaN(value) && value > 0) {
                      updateDataTreatment({
                        implementedQualityChanges: {
                          ...documentationData.modelDesign.dataTreatment.implementedQualityChanges,
                          rowsToShow: value,
                        },
                      });
                    }
                  }}
                  className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                />
                <span className="text-sm text-gray-600">rows</span>
              </div>
            </div>

            {documentationData.modelDesign.dataTreatment.implementedQualityChanges.columnStats.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full border border-gray-300 text-sm">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Column</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Type</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Missing</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Unique</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Mean</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Median</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Mode</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Std</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Var</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Min</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">p5%</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">p25%</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">p50%</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">p75%</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">p95%</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">p99%</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Max</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documentationData.modelDesign.dataTreatment.implementedQualityChanges.columnStats
                      .slice(0, documentationData.modelDesign.dataTreatment.implementedQualityChanges.rowsToShow)
                      .map((row, index) => (
                        <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{row.Column}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{row.Type}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{row.Missing}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{row.Unique}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row.Mean === 'number' ? row.Mean.toFixed(4) : row.Mean}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row.Median === 'number' ? row.Median.toFixed(4) : row.Median}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{row.Mode}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row.Std === 'number' ? row.Std.toFixed(4) : row.Std}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row.Var === 'number' ? row.Var.toFixed(4) : row.Var}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row.Min === 'number' ? row.Min.toFixed(4) : row.Min}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row['p5%'] === 'number' ? row['p5%'].toFixed(4) : row['p5%']}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row['p25%'] === 'number' ? row['p25%'].toFixed(4) : row['p25%']}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row['p50%'] === 'number' ? row['p50%'].toFixed(4) : row['p50%']}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row['p75%'] === 'number' ? row['p75%'].toFixed(4) : row['p75%']}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row['p95%'] === 'number' ? row['p95%'].toFixed(4) : row['p95%']}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row['p99%'] === 'number' ? row['p99%'].toFixed(4) : row['p99%']}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row.Max === 'number' ? row.Max.toFixed(4) : row.Max}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-gray-500 italic">No column stats data available</p>
            )}
          </div>
        </div>
        )}
          </>
        )}
      </CollapsibleSection>

      {/* 4. DATA INSIGHTS Section */}
      <CollapsibleSection sectionNumber={4} sectionTitle="DATA INSIGHTS" defaultExpanded={false}>
        {() => {
          const hasDataInsights = hasDataInsightsData();
          
          // Debug logging
          if (documentationData.dataInsights) {
            console.log('DocumentationViewer - Data insights available:', {
              bivariateAnalysis: !!documentationData.dataInsights.bivariateAnalysis,
              ivAnalysis: !!documentationData.dataInsights.ivAnalysis,
              correlationAnalysis: !!documentationData.dataInsights.correlationAnalysis,
              correlationAnalysisNumeric: !!documentationData.dataInsights.correlationAnalysisNumeric,
              correlationAnalysisNumericData: documentationData.dataInsights.correlationAnalysisNumeric
            });
          }
          
          return (
            <>

            {!hasDataInsights ? (
              <div className="pl-6">
                <p className="text-gray-700">You didn't derive any insights on this data! Go to Data Insights page and generate your insights.</p>
              </div>
            ) : (
              <div className="pl-6 space-y-6">
                  {/* Bivariate Analysis - Dynamic numbering */}
                  {documentationData.dataInsights.bivariateAnalysis && (
                <div className="space-y-4">
                  <div className="space-y-1">
                    <h4 className="text-lg font-bold text-gray-800">
                      {(() => {
                        // Determine section number dynamically based on what sections exist
                        const sectionIndex = availableSections.findIndex(s => s.key === 'bivariateAnalysis');
                        return `4.${sectionIndex + 1} Bivariate Analysis`;
                      })()}
                    </h4>
                  </div>

                  {/* Bullet point insights */}
                  {documentationData.dataInsights.bivariateAnalysis.insights && 
                   documentationData.dataInsights.bivariateAnalysis.insights.length > 0 && (
                    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
                      <EditableField
                        value={documentationData.dataInsights.bivariateAnalysis.insights.map(insight => `- ${insight}`).join('\n')}
                        onSave={(newValue) => {
                          updateDataInsights({
                            bivariateAnalysis: {
                              ...documentationData.dataInsights.bivariateAnalysis,
                              insights: newValue.split('\n').map(line => line.trim()).filter(line => line).map(line => line.startsWith('- ') ? line.substring(2) : line),
                            },
                          });
                        }}
                        multiline={true}
                        renderBullets={true}
                      />
                    </div>
                  )}

                  {/* EDA Report - Dynamic numbering */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h5 className="text-md font-semibold text-gray-900">
                        {(() => {
                          // Determine subsection number dynamically
                          const sectionIndex = availableSections.findIndex(s => s.key === 'bivariateAnalysis');
                          return `4.${sectionIndex + 1}.1 Insights`;
                        })()}
                      </h5>
                      {/* Rows filter - Dropdown */}
                      <div className="flex items-center space-x-2">
                        <label htmlFor="bivariateEdaRows" className="text-sm text-gray-600">Show</label>
                        <select
                          id="bivariateEdaRows"
                          value={documentationData.dataInsights.bivariateAnalysis.rowsToShow || 'used_features'}
                          onChange={(e) => {
                            const value = e.target.value === 'all' ? 'all' : 
                                         e.target.value === 'used_features' ? 'used_features' : 
                                         parseInt(e.target.value);
                            if (documentationData.dataInsights.bivariateAnalysis) {
                              updateDataInsights({
                                bivariateAnalysis: {
                                  ...documentationData.dataInsights.bivariateAnalysis,
                                  rowsToShow: value,
                                },
                              });
                            }
                          }}
                          className="px-2 py-1 border border-gray-300 rounded text-sm"
                        >
                          <option value="5">5</option>
                          <option value="20">20</option>
                          <option value="100">100</option>
                          <option value="all">All</option>
                          <option value="used_features">Features used in modelling</option>
                        </select>
                      </div>
                    </div>
                    {documentationData.dataInsights.bivariateAnalysis.edaReport && 
                     documentationData.dataInsights.bivariateAnalysis.edaReport.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="min-w-full border border-gray-300">
                          <thead className="bg-gray-100">
                            <tr>
                              <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Variable</th>
                              <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Event rate range</th>
                              <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Insight</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filterDataInsightsRows(
                              documentationData.dataInsights.bivariateAnalysis.edaReport,
                              documentationData.dataInsights.bivariateAnalysis.rowsToShow || 'used_features'
                            ).map((row, index) => (
                                <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                  <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{row.Variable}</td>
                                  <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{row['Event rate range']}</td>
                                  <td className="px-4 py-2 border-b border-gray-200 text-gray-700">{row.Insight}</td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-gray-500 italic">No EDA report data available</p>
                    )}
                  </div>
                </div>
              )}

              {/* Information Value (IV) - Dynamic numbering based on what sections exist */}
              {documentationData.dataInsights.ivAnalysis && (
                <div className="space-y-4">
                  <div className="space-y-1">
                    <h4 className="text-lg font-bold text-gray-800">
                      {(() => {
                        // Determine section number dynamically based on what sections exist
                        const sectionIndex = availableSections.findIndex(s => s.key === 'ivAnalysis');
                        return `4.${sectionIndex + 1} Information Value (IV)`;
                      })()}
                    </h4>
                  </div>

                  {/* Bullet point insights */}
                  {documentationData.dataInsights.ivAnalysis.insights && 
                   documentationData.dataInsights.ivAnalysis.insights.length > 0 && (
                    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
                      <EditableField
                        value={documentationData.dataInsights.ivAnalysis.insights.map(insight => `- ${insight}`).join('\n')}
                        onSave={(newValue) => {
                          updateDataInsights({
                            ivAnalysis: {
                              ...documentationData.dataInsights.ivAnalysis,
                              insights: newValue.split('\n').map(line => line.trim()).filter(line => line).map(line => line.startsWith('- ') ? line.substring(2) : line),
                            },
                          });
                        }}
                        multiline={true}
                        renderBullets={true}
                      />
                    </div>
                  )}

                  {/* 4.x.1 EDA Report */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h5 className="text-md font-semibold text-gray-900">
                        {(() => {
                          // Determine subsection number dynamically
                          const sectionIndex = availableSections.findIndex(s => s.key === 'ivAnalysis');
                          return `4.${sectionIndex + 1}.1 Insights`;
                        })()}
                      </h5>
                      {/* Rows filter - Dropdown */}
                      <div className="flex items-center space-x-2">
                        <label htmlFor="ivEdaRows" className="text-sm text-gray-600">Show</label>
                        <select
                          id="ivEdaRows"
                          value={documentationData.dataInsights.ivAnalysis.rowsToShow || 'used_features'}
                          onChange={(e) => {
                            const value = e.target.value === 'all' ? 'all' : 
                                         e.target.value === 'used_features' ? 'used_features' : 
                                         parseInt(e.target.value);
                            if (documentationData.dataInsights.ivAnalysis) {
                              updateDataInsights({
                                ivAnalysis: {
                                  ...documentationData.dataInsights.ivAnalysis,
                                  rowsToShow: value,
                                },
                              });
                            }
                          }}
                          className="px-2 py-1 border border-gray-300 rounded text-sm"
                        >
                          <option value="5">5</option>
                          <option value="20">20</option>
                          <option value="100">100</option>
                          <option value="all">All</option>
                          <option value="used_features">Features used in modelling</option>
                        </select>
                      </div>
                    </div>
                    {documentationData.dataInsights.ivAnalysis.edaReport && 
                     documentationData.dataInsights.ivAnalysis.edaReport.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="min-w-full border border-gray-300">
                          <thead className="bg-gray-100">
                            <tr>
                              <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Variable</th>
                              <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">IV</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filterDataInsightsRows(
                              documentationData.dataInsights.ivAnalysis.edaReport,
                              documentationData.dataInsights.ivAnalysis.rowsToShow || 'used_features'
                            ).map((row, index) => (
                                <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                  <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{row.Variable}</td>
                                  <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{typeof row.IV === 'number' ? row.IV.toFixed(4) : row.IV}</td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-gray-500 italic">No EDA report data available</p>
                    )}
                  </div>
                </div>
              )}
        
              {/* Correlation Matrix - Dynamic numbering based on what sections exist */}
              {documentationData.dataInsights.correlationAnalysis && (
                <div className="space-y-4">
                  <div className="space-y-1">
                    <h4 className="text-lg font-bold text-gray-800">
                      {(() => {
                        // Determine section number dynamically based on what sections exist
                        const sectionIndex = availableSections.findIndex(s => s.key === 'correlationAnalysis');
                        return `4.${sectionIndex + 1} Correlation Matrix`;
                      })()}
                    </h4>
            </div>

                  {/* Bullet point insights */}
                  {documentationData.dataInsights.correlationAnalysis.insights && 
                   documentationData.dataInsights.correlationAnalysis.insights.length > 0 && (
                    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
                      <EditableField
                        value={documentationData.dataInsights.correlationAnalysis.insights.map(insight => `- ${insight}`).join('\n')}
                        onSave={(newValue) => {
                          updateDataInsights({
                            correlationAnalysis: {
                              ...documentationData.dataInsights.correlationAnalysis,
                              insights: newValue.split('\n').map(line => line.trim()).filter(line => line).map(line => line.startsWith('- ') ? line.substring(2) : line),
                            },
                          });
                        }}
                        multiline={true}
                        renderBullets={true}
                      />
          </div>
                  )}


                  {/* 4.x.1 EDA Report */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h5 className="text-md font-semibold text-gray-900">
                        {(() => {
                          // Determine subsection number dynamically
                          const sectionIndex = availableSections.findIndex(s => s.key === 'correlationAnalysis');
                          return `4.${sectionIndex + 1}.1 Insights`;
                        })()}
                      </h5>
                      {/* Rows filter - Dropdown */}
                      <div className="flex items-center space-x-2">
                        <label htmlFor="correlationEdaRows" className="text-sm text-gray-600">Show</label>
                        <select
                          id="correlationEdaRows"
                          value={documentationData.dataInsights.correlationAnalysis.rowsToShow || 'used_features'}
                          onChange={(e) => {
                            const value = e.target.value === 'all' ? 'all' : 
                                         e.target.value === 'used_features' ? 'used_features' : 
                                         parseInt(e.target.value);
                            if (documentationData.dataInsights.correlationAnalysis) {
                              updateDataInsights({
                                correlationAnalysis: {
                                  ...documentationData.dataInsights.correlationAnalysis,
                                  rowsToShow: value,
                                },
                              });
                            }
                          }}
                          className="px-2 py-1 border border-gray-300 rounded text-sm"
                        >
                          <option value="5">5</option>
                          <option value="20">20</option>
                          <option value="100">100</option>
                          <option value="all">All</option>
                          <option value="used_features">Features used in modelling</option>
                        </select>
                      </div>
                    </div>
                    {documentationData.dataInsights.correlationAnalysis.edaReport && 
                     documentationData.dataInsights.correlationAnalysis.edaReport.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="min-w-full border border-gray-300">
                          <thead className="bg-gray-100">
                            <tr>
                              {/* Dynamic columns: Variable + all other variables */}
                              {(() => {
                                const firstRow = documentationData.dataInsights.correlationAnalysis.edaReport[0];
                                return Object.keys(firstRow).map((key) => (
                                  <th key={key} className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">
                                    {key}
                                  </th>
                                ));
                              })()}
                            </tr>
                          </thead>
                          <tbody>
                            {filterDataInsightsRows(
                              documentationData.dataInsights.correlationAnalysis.edaReport,
                              documentationData.dataInsights.correlationAnalysis.rowsToShow || 'used_features'
                            ).map((row, index) => (
                                <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                  {Object.keys(row).map((key) => (
                                    <td key={key} className="px-4 py-2 border-b border-gray-200 text-gray-900">
                                      {typeof row[key] === 'number' ? row[key].toFixed(4) : row[key]}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-gray-500 italic">No EDA report data available</p>
                    )}
                  </div>
                </div>
              )}

              {/* Correlation Analysis (Numeric) - Dynamic numbering based on what sections exist - NEW */}
              {documentationData.dataInsights.correlationAnalysisNumeric && (
                <div className="space-y-4">
                  <div className="space-y-1">
                    <h4 className="text-lg font-bold text-gray-800">
                      {(() => {
                        // Determine section number dynamically based on what sections exist
                        const sectionIndex = availableSections.findIndex(s => s.key === 'correlationAnalysisNumeric');
                        return `4.${sectionIndex + 1} Correlation Analysis`;
                      })()}
                    </h4>
                  </div>

                  {/* Bullet point insights */}
                  {documentationData.dataInsights.correlationAnalysisNumeric.insights && 
                   documentationData.dataInsights.correlationAnalysisNumeric.insights.length > 0 && (
                    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
                      <EditableField
                        value={documentationData.dataInsights.correlationAnalysisNumeric.insights.map(insight => `- ${insight}`).join('\n')}
                        onSave={(newValue) => {
                          updateDataInsights({
                            correlationAnalysisNumeric: {
                              ...documentationData.dataInsights.correlationAnalysisNumeric,
                              insights: newValue.split('\n').map(line => line.trim()).filter(line => line).map(line => line.startsWith('- ') ? line.substring(2) : line),
                            },
                          });
                        }}
                        multiline={true}
                        renderBullets={true}
                      />
                    </div>
                  )}

                  {/* 4.x.1 EDA Report */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h5 className="text-md font-semibold text-gray-700">
                        {(() => {
                          const sectionIndex = availableSections.findIndex(s => s.key === 'correlationAnalysisNumeric');
                          return `4.${sectionIndex + 1}.1 Insights`;
                        })()}
                      </h5>
                      <div className="flex items-center gap-2">
                        <label className="text-sm text-gray-600">Show</label>
                        <select
                          value={documentationData.dataInsights.correlationAnalysisNumeric.rowsToShow || 'used_features'}
                          onChange={(e) => {
                            const value = e.target.value === 'all' ? 'all' : 
                                         e.target.value === 'used_features' ? 'used_features' : 
                                         parseInt(e.target.value);
                            if (documentationData.dataInsights.correlationAnalysisNumeric) {
                              updateDataInsights({
                                correlationAnalysisNumeric: {
                                  ...documentationData.dataInsights.correlationAnalysisNumeric,
                                  rowsToShow: value,
                                },
                              });
                            }
                          }}
                          className="px-2 py-1 border border-gray-300 rounded text-sm"
                        >
                          <option value="5">5</option>
                          <option value="20">20</option>
                          <option value="100">100</option>
                          <option value="all">All</option>
                          <option value="used_features">Features used in modelling</option>
                        </select>
                      </div>
                    </div>

                    {documentationData.dataInsights.correlationAnalysisNumeric.edaReport && 
                     documentationData.dataInsights.correlationAnalysisNumeric.edaReport.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="min-w-full bg-white border border-gray-200">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase border-b">Variable Name</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase border-b">Type of Variable</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase border-b">Pearson Coefficient</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase border-b">Spearman Coefficient</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-200">
                            {filterDataInsightsRows(
                              documentationData.dataInsights.correlationAnalysisNumeric.edaReport,
                              documentationData.dataInsights.correlationAnalysisNumeric.rowsToShow || 'used_features'
                            ).map((row: any, index: number) => (
                                <tr key={index} className="hover:bg-gray-50">
                                  <td className="px-4 py-2 text-sm text-gray-900">{row['Variable Name'] || ''}</td>
                                  <td className="px-4 py-2 text-sm text-gray-700">{row['Type of Variable'] || ''}</td>
                                  <td className="px-4 py-2 text-sm text-gray-700">
                                    {typeof row['Pearson Coefficient'] === 'number' 
                                      ? row['Pearson Coefficient'].toFixed(4) 
                                      : row['Pearson Coefficient'] || ''}
                                  </td>
                                  <td className="px-4 py-2 text-sm text-gray-700">
                                    {typeof row['Spearman Coefficient'] === 'number' 
                                      ? row['Spearman Coefficient'].toFixed(4) 
                                      : row['Spearman Coefficient'] || ''}
                                  </td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-gray-500 text-sm">No EDA report data available.</div>
                    )}
                  </div>
                </div>
              )}

              {/* VIF Analysis - Dynamic numbering based on what sections exist - NEW */}
              {documentationData.dataInsights.vifAnalysis && (
                <div className="space-y-4">
                  <div className="space-y-1">
                    <h4 className="text-lg font-bold text-gray-800">
                      {(() => {
                        // Determine section number dynamically based on what sections exist
                        const sectionIndex = availableSections.findIndex(s => s.key === 'vifAnalysis');
                        return `4.${sectionIndex + 1} Variable Inflation Factor (VIF)`;
                      })()}
                    </h4>
                  </div>

                  {/* Bullet point insights */}
                  {documentationData.dataInsights.vifAnalysis.insights && 
                   documentationData.dataInsights.vifAnalysis.insights.length > 0 && (
                    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
                      <EditableField
                        value={documentationData.dataInsights.vifAnalysis.insights.map(insight => `- ${insight}`).join('\n')}
                        onSave={(newValue) => {
                          updateDataInsights({
                            vifAnalysis: {
                              ...documentationData.dataInsights.vifAnalysis,
                              insights: newValue.split('\n').map(line => line.trim()).filter(line => line).map(line => line.startsWith('- ') ? line.substring(2) : line),
                            },
                          });
                        }}
                        multiline={true}
                        renderBullets={true}
                      />
                    </div>
                  )}

                  {/* 4.x.1 EDA Report */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h5 className="text-md font-semibold text-gray-700">
                        {(() => {
                          const sectionIndex = availableSections.findIndex(s => s.key === 'vifAnalysis');
                          return `4.${sectionIndex + 1}.1 Insights`;
                        })()}
                      </h5>
                      <div className="flex items-center gap-2">
                        <label className="text-sm text-gray-600">Show</label>
                        <select
                          value={documentationData.dataInsights.vifAnalysis.rowsToShow || 'used_features'}
                          onChange={(e) => {
                            const value = e.target.value === 'all' ? 'all' : 
                                         e.target.value === 'used_features' ? 'used_features' : 
                                         parseInt(e.target.value);
                            if (documentationData.dataInsights.vifAnalysis) {
                              updateDataInsights({
                                vifAnalysis: {
                                  ...documentationData.dataInsights.vifAnalysis,
                                  rowsToShow: value,
                                },
                              });
                            }
                          }}
                          className="px-2 py-1 border border-gray-300 rounded text-sm"
                        >
                          <option value="5">5</option>
                          <option value="20">20</option>
                          <option value="100">100</option>
                          <option value="all">All</option>
                          <option value="used_features">Features used in modelling</option>
                        </select>
                      </div>
                    </div>

                    {documentationData.dataInsights.vifAnalysis.edaReport && 
                     documentationData.dataInsights.vifAnalysis.edaReport.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="min-w-full bg-white border border-gray-200">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase border-b">Variable</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase border-b">VIF</th>
                              <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase border-b">Interpretation</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-200">
                            {filterDataInsightsRows(
                              documentationData.dataInsights.vifAnalysis.edaReport,
                              documentationData.dataInsights.vifAnalysis.rowsToShow || 'used_features'
                            ).map((row: any, index: number) => (
                                <tr key={index} className="hover:bg-gray-50">
                                  <td className="px-4 py-2 text-sm text-gray-900">{row['Variable'] || ''}</td>
                                  <td className="px-4 py-2 text-sm text-gray-700">
                                    {typeof row['VIF'] === 'number' 
                                      ? row['VIF'].toFixed(2) 
                                      : row['VIF'] || ''}
                                  </td>
                                  <td className="px-4 py-2 text-sm text-gray-700">{row['Interpretation'] || ''}</td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-gray-500 text-sm">No EDA report data available.</div>
                    )}
                  </div>
                </div>
              )}
              </div>
            )}
          </>
        );
        }}
      </CollapsibleSection>

      {/* SEGMENTATION Section */}
      <CollapsibleSection sectionNumber={5} sectionTitle="SEGMENTATION" defaultExpanded={false}>
        {() => (
          <>
      
      {!hasSegmentationData() ? (
        <div className="pl-6">
          <p className="text-gray-700">You didn't do Segmentation over your data! Go to Segmentation page and make segments of your data.</p>
        </div>
      ) : documentationData.modelDesign.segmentation.hasSegmentation ? (
        <>

        <div className="pl-6 space-y-6">
          {/* Understand the Segments Section */}
          {documentationData.modelDesign.segmentation.understanding?.content && (
            <div className="space-y-3">
              <h5 className="text-md font-semibold text-gray-800">Understand the Segments</h5>
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <EditableField
                  value={documentationData.modelDesign.segmentation.understanding.content}
                  onSave={(newValue) => {
                    updateSegmentation({
                      understanding: {
                        content: newValue,
                        lastGenerated: documentationData.modelDesign.segmentation.understanding?.lastGenerated || null,
                      },
                    });
                  }}
                  multiline={true}
                  renderBullets={true}
                />
              </div>
              {documentationData.modelDesign.segmentation.understanding.lastGenerated && (
                <p className="text-xs text-gray-500 italic">
                  Generated on: {new Date(documentationData.modelDesign.segmentation.understanding.lastGenerated).toLocaleString()}
                </p>
              )}
            </div>
          )}

          {/* Variables used */}
          {documentationData.modelDesign.segmentation.variablesUsed && documentationData.modelDesign.segmentation.variablesUsed.length > 0 && (
            <div className="space-y-2">
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <span className="font-semibold text-gray-800">Variables used: </span>
                <span className="text-gray-700">{documentationData.modelDesign.segmentation.variablesUsed.join(', ')}</span>
              </div>
            </div>
          )}

          {/* Method used */}
          {documentationData.modelDesign.segmentation.method && (
            <div className="space-y-2">
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <span className="font-semibold text-gray-800">Method used: </span>
                <span className="text-gray-700">{String(documentationData.modelDesign.segmentation.method).toUpperCase()}</span>
              </div>
            </div>
          )}

          {/* Segments */}
          {documentationData.modelDesign.segmentation.segments.map((segment, index) => (
            <div key={index} className="space-y-3">
              {/* Segment Heading with Rule */}
              <h5 className="text-md font-semibold text-gray-900">
                Segment {segment.segmentNumber}: {segment.rule}
              </h5>
              
              {/* Segment Stats Table */}
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b-2 border-gray-300">
                      <th className="px-4 py-2 text-left font-semibold text-gray-700">Total</th>
                      <th className="px-4 py-2 text-left font-semibold text-gray-700">Event Rate</th>
                      <th className="px-4 py-2 text-left font-semibold text-gray-700">Segment Distribution</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="px-4 py-2 text-gray-900 font-medium">
                        {segment.total.toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-blue-600 font-semibold">
                        {segment.eventRate.toFixed(2)}%
                      </td>
                      <td className="px-4 py-2 text-green-600 font-semibold">
                        {segment.segmentDistribution.toFixed(2)}%
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          ))}

          {/* Segment Sizes and Proportions Charts - Side by Side */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            {/* Chart 1: Segment Sizes (Bar Chart with Line for Event Rate) */}
            <div className="space-y-2">
              <h5 className="text-md font-semibold text-gray-800">Segment Sizes</h5>
              <div className="px-4 pb-4" style={{ height: '280px' }}>
                <Bar
                  data={{
                    labels: documentationData.modelDesign.segmentation.segments.map(s => `Segment ${s.segmentNumber}`),
                    datasets: [
                      {
                        type: 'bar' as const,
                        label: 'Total',
                        data: documentationData.modelDesign.segmentation.segments.map(s => s.total),
                        backgroundColor: [
                          'rgba(99, 102, 241, 0.8)',
                          'rgba(59, 130, 246, 0.8)',
                          'rgba(16, 185, 129, 0.8)',
                          'rgba(245, 158, 11, 0.8)',
                          'rgba(236, 72, 153, 0.8)',
                          'rgba(239, 68, 68, 0.8)'
                        ],
                        borderColor: [
                          'rgb(99, 102, 241)',
                          'rgb(59, 130, 246)',
                          'rgb(16, 185, 129)',
                          'rgb(245, 158, 11)',
                          'rgb(236, 72, 153)',
                          'rgb(239, 68, 68)'
                        ],
                        borderWidth: 2,
                        borderRadius: 6,
                        yAxisID: 'y'
                      },
                      ...(documentationData.modelDesign.segmentation.segmentSizesChart?.eventRates && documentationData.modelDesign.segmentation.segmentSizesChart.eventRates.length > 0 ? [{
                        type: 'line' as const,
                        label: 'Event Rate',
                        data: documentationData.modelDesign.segmentation.segmentSizesChart.eventRates,
                        borderColor: 'rgb(37, 99, 235)',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        borderWidth: 3,
                        yAxisID: 'y1',
                        tension: 0.4
                      }] as any : [])
                    ]
                  }}
                  options={{ 
                    responsive: true, 
                    maintainAspectRatio: false,
                    interaction: {
                      mode: 'index' as const,
                      intersect: false
                    },
                    plugins: { 
                      legend: { 
                        display: true,
                        position: 'top' as const,
                        labels: {
                          padding: 10,
                          font: {
                            size: 11
                          },
                          usePointStyle: true,
                          boxHeight: 6
                        }
                      },
                      tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: 'rgba(255, 255, 255, 0.2)',
                        borderWidth: 1,
                        callbacks: {
                          label: function(context: any) {
                            let label = context.dataset.label || '';
                            if (label) {
                              label += ': ';
                            }
                            if (context.parsed.y !== null) {
                              if (context.dataset.yAxisID === 'y1') {
                                const value = context.parsed.y;
                                if (value <= 1) {
                                  label += (value * 100).toFixed(2) + '%';
                                } else {
                                  label += value.toFixed(2);
                                }
                              } else {
                                label += context.parsed.y.toLocaleString();
                              }
                            }
                            return label;
                          }
                        }
                      }
                    },
                    scales: {
                      y: {
                        type: 'linear' as const,
                        display: true,
                        position: 'left' as const,
                        beginAtZero: true,
                        title: {
                          display: true,
                          text: 'Total Records',
                          font: {
                            size: 10
                          }
                        },
                        grid: {
                          color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                          font: {
                            size: 10
                          }
                        }
                      },
                      ...(documentationData.modelDesign.segmentation.segmentSizesChart?.eventRates && documentationData.modelDesign.segmentation.segmentSizesChart.eventRates.length > 0 ? {
                        y1: {
                          type: 'linear' as const,
                          display: true,
                          position: 'right' as const,
                          beginAtZero: true,
                          title: {
                            display: true,
                            text: 'Event Rate',
                            font: {
                              size: 10
                            }
                          },
                          grid: {
                            drawOnChartArea: false
                          },
                          ticks: {
                            font: {
                              size: 10
                            }
                          }
                        }
                      } : {}),
                      x: {
                        grid: {
                          display: false
                        },
                        ticks: {
                          font: {
                            size: 10
                          }
                        }
                      }
                    }
                  }}
                />
              </div>
            </div>

            {/* Chart 2: Segment Proportions (Pie Chart) */}
            <div className="space-y-2">
              <h5 className="text-md font-semibold text-gray-800">Segment Proportions</h5>
              <div className="px-4 pb-4" style={{ height: '280px' }}>
                <Pie
                  data={{
                    labels: documentationData.modelDesign.segmentation.segments.map(s => `Segment ${s.segmentNumber}`),
                    datasets: [{
                      label: 'Proportion',
                      data: documentationData.modelDesign.segmentation.segments.map(s => s.segmentDistribution / 100), // Convert percentage to decimal
                      backgroundColor: documentationData.modelDesign.segmentation.segmentProportionsChart?.colors || [
                        'rgba(99, 102, 241, 0.8)',
                        'rgba(59, 130, 246, 0.8)',
                        'rgba(16, 185, 129, 0.8)',
                        'rgba(245, 158, 11, 0.8)',
                        'rgba(236, 72, 153, 0.8)',
                        'rgba(239, 68, 68, 0.8)'
                      ],
                      borderColor: [
                        'rgb(99, 102, 241)',
                        'rgb(59, 130, 246)',
                        'rgb(16, 185, 129)',
                        'rgb(245, 158, 11)',
                        'rgb(236, 72, 153)',
                        'rgb(239, 68, 68)'
                      ],
                      borderWidth: 2
                    }]
                  }}
                  options={{ 
                    responsive: true, 
                    maintainAspectRatio: false,
                    plugins: { 
                      legend: { 
                        position: 'bottom',
                        labels: {
                          padding: 10,
                          font: {
                            size: 11
                          },
                          usePointStyle: true,
                          pointStyle: 'circle',
                          boxHeight: 8
                        }
                      },
                      tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: 'rgba(255, 255, 255, 0.2)',
                        borderWidth: 1,
                        callbacks: {
                          label: function(context: any) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const percentage = (value * 100).toFixed(1);
                            return `${label}: ${percentage}%`;
                          }
                        }
                      }
                    }
                  }}
                />
              </div>
            </div>
          </div>

          {/* IV Visualization Charts Section */}
          {(() => {
            const ivReport = documentationData.modelDesign.segmentation.ivVisualizationCharts?.ivReport;
            if (!ivReport) return null;
            
            return (
            <div className="space-y-4 mt-6">
              <h5 className="text-md font-semibold text-gray-800">IV Visualization Charts</h5>
              
              {/* Grid of IV Charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Row 1, Col 1: Weight of Evidence */}
                <div className="border border-gray-200 rounded-lg p-4">
                  <h6 className="font-semibold text-gray-900 mb-3 text-sm">Weight of Evidence by Segment</h6>
                  <div className="h-56">
                    <Bar
                      data={{
                        labels: ivReport.table.map((r: any) => `Segment_${r.segment_id + 1}`),
                        datasets: [{
                          label: 'WoE',
                          data: ivReport.table.map((r: any) => r.woe),
                          backgroundColor: ivReport.table.map((r: any) => 
                            r.woe > 0 ? 'rgba(34, 197, 94, 0.8)' : 'rgba(239, 68, 68, 0.8)'
                          ),
                          borderColor: ivReport.table.map((r: any) => 
                            r.woe > 0 ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)'
                          ),
                          borderWidth: 1
                        }]
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { display: false },
                          tooltip: {
                            callbacks: {
                              label: (context) => `WoE: ${context.parsed.y.toFixed(3)}`
                            }
                          }
                        },
                        scales: {
                          y: {
                            title: { display: true, text: 'Weight of Evidence (WOE)' },
                            grid: {
                              color: (context: any) => context.tick.value === 0 ? 'rgba(0, 0, 0, 0.3)' : 'rgba(0, 0, 0, 0.1)'
                            }
                          },
                          x: { title: { display: true, text: 'Segment' } }
                        }
                      }}
                    />
                  </div>
                </div>

                {/* Row 1, Col 2: IV Components */}
                <div className="border border-gray-200 rounded-lg p-4">
                  <h6 className="font-semibold text-gray-900 mb-3 text-sm">IV Components by Segment</h6>
                  <div className="h-56">
                    <Bar
                      data={{
                        labels: ivReport.table.map((r: any) => `Segment_${r.segment_id + 1}`),
                        datasets: [{
                          label: 'IV Component',
                          data: ivReport.table.map((r: any) => r.iv_contribution),
                          backgroundColor: 'rgba(34, 197, 94, 0.8)',
                          borderColor: 'rgb(34, 197, 94)',
                          borderWidth: 1
                        }]
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { display: false },
                          tooltip: {
                            callbacks: {
                              label: (context) => `IV: ${context.parsed.y.toFixed(4)}`
                            }
                          }
                        },
                        scales: {
                          y: {
                            beginAtZero: true,
                            title: { display: true, text: 'IV Component' }
                          },
                          x: { title: { display: true, text: 'Segment' } }
                        }
                      }}
                    />
                  </div>
                </div>

                {/* Row 2, Col 1: Distribution of Good vs Bad */}
                <div className="border border-gray-200 rounded-lg p-4">
                  <h6 className="font-semibold text-gray-900 mb-3 text-sm">Distribution of Good vs Bad by Segment</h6>
                  <div className="h-56">
                    <Bar
                      data={{
                        labels: ivReport.table.map((r: any) => `Segment_${r.segment_id + 1}`),
                        datasets: [
                          {
                            label: '% of Total Good',
                            data: ivReport.table.map((r: any) => r.dist_goods * 100),
                            backgroundColor: 'rgba(34, 197, 94, 0.8)',
                            borderColor: 'rgb(34, 197, 94)',
                            borderWidth: 1
                          },
                          {
                            label: '% of Total Bad',
                            data: ivReport.table.map((r: any) => r.dist_bads * 100),
                            backgroundColor: 'rgba(239, 68, 68, 0.8)',
                            borderColor: 'rgb(239, 68, 68)',
                            borderWidth: 1
                          }
                        ]
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { 
                            display: true,
                            position: 'top' as const,
                            labels: { boxWidth: 12, padding: 10, font: { size: 10 } }
                          },
                          tooltip: {
                            callbacks: {
                              label: (context) => `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`
                            }
                          }
                        },
                        scales: {
                          y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Percentage of Total' },
                            ticks: { callback: (value) => `${value}%` }
                          },
                          x: { title: { display: true, text: 'Segment' } }
                        }
                      }}
                    />
                  </div>
                </div>

                {/* Row 2, Col 2: Bad Rate */}
                <div className="border border-gray-200 rounded-lg p-4">
                  <h6 className="font-semibold text-gray-900 mb-3 text-sm">Bad Rate by Segment</h6>
                  <div className="h-56">
                    <Bar
                      data={{
                        labels: ivReport.table.map((r: any) => `Segment_${r.segment_id + 1}`),
                        datasets: [{
                          label: 'Bad Rate',
                          data: ivReport.table.map((r: any) => r.bad_rate),
                          backgroundColor: 'rgba(251, 191, 36, 0.8)',
                          borderColor: 'rgb(251, 191, 36)',
                          borderWidth: 1
                        }]
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { display: false },
                          tooltip: {
                            callbacks: {
                              label: (context) => `Bad Rate: ${(context.parsed.y * 100).toFixed(1)}%`
                            }
                          }
                        },
                        scales: {
                          y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Bad Rate' },
                            ticks: { callback: (value) => `${(Number(value) * 100).toFixed(0)}%` }
                          },
                          x: { title: { display: true, text: 'Segment' } }
                        }
                      }}
                    />
                  </div>
                </div>

                {/* Row 3, Col 1: Population Distribution Pie Chart */}
                <div className="border border-gray-200 rounded-lg p-4">
                  <h6 className="font-semibold text-gray-900 mb-3 text-sm">Population Distribution by Segment</h6>
                  <div className="h-56 flex items-center justify-center">
                    <div className="w-full h-full max-w-xs mx-auto">
                      <MemoizedPie
                        data={{
                          labels: ivReport.table.map((r: any) => `Segment_${r.segment_id + 1}`),
                          datasets: [{
                            data: ivReport.table.map((r: any) => r.accounts),
                            backgroundColor: [
                              'rgba(34, 197, 94, 0.8)',
                              'rgba(59, 130, 246, 0.8)',
                              'rgba(251, 191, 36, 0.8)',
                              'rgba(239, 68, 68, 0.8)',
                              'rgba(168, 85, 247, 0.8)',
                              'rgba(236, 72, 153, 0.8)'
                            ],
                            borderColor: '#fff',
                            borderWidth: 2
                          }]
                        }}
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: {
                            legend: {
                              display: true,
                              position: 'bottom' as const,
                              labels: { boxWidth: 12, padding: 8, font: { size: 10 } }
                            },
                            tooltip: {
                              callbacks: {
                                label: (context) => {
                                  const label = context.label || '';
                                  const value = context.parsed || 0;
                                  const total = ivReport.totals.N;
                                  const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : '0';
                                  return `${label}: ${value.toLocaleString()} (${percentage}%)`;
                                }
                              }
                            }
                          }
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* Row 3, Col 2: IV Strength Benchmark */}
                {documentationData.modelDesign.segmentation.ivVisualizationCharts?.ivStrength && (
                  <div className="border border-gray-200 rounded-lg p-4">
                    <h6 className="font-semibold text-gray-900 mb-3 text-sm">
                      IV Strength: {documentationData.modelDesign.segmentation.ivVisualizationCharts.ivStrength.value.toFixed(4)} ({documentationData.modelDesign.segmentation.ivVisualizationCharts.ivStrength.label})
                    </h6>
                    <div className="h-56 relative">
                      <Bar
                        data={{
                          labels: ['Not Useful\n(0-0.02)', 'Weak\n(0.02-0.1)', 'Medium\n(0.1-0.3)', 'Strong\n(0.3-0.5)', 'Suspicious\n(>0.5)'],
                          datasets: [{
                            label: 'IV Range',
                            data: [0.02, 0.08, 0.2, 0.2, 0.5],
                            backgroundColor: [
                              'rgba(239, 68, 68, 0.7)',
                              'rgba(59, 130, 246, 0.7)',
                              'rgba(251, 191, 36, 0.7)',
                              'rgba(34, 197, 94, 0.7)',
                              'rgba(127, 29, 29, 0.7)'
                            ],
                            borderColor: [
                              'rgb(239, 68, 68)',
                              'rgb(59, 130, 246)',
                              'rgb(251, 191, 36)',
                              'rgb(34, 197, 94)',
                              'rgb(127, 29, 29)'
                            ],
                            borderWidth: 1
                          }]
                        }}
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: {
                            legend: { display: false },
                            tooltip: {
                              callbacks: {
                                label: (context: any) => {
                                  const labels = ['0-0.02', '0.02-0.1', '0.1-0.3', '0.3-0.5', '>0.5'];
                                  return `IV Range: ${labels[context.dataIndex]}`;
                                }
                              }
                            }
                          },
                          scales: {
                            y: {
                              beginAtZero: true,
                              max: 0.6,
                              title: { display: true, text: 'IV Range' }
                            },
                            x: {
                              title: { display: true, text: 'IV Strength Categories' }
                            }
                          }
                        }}
                      />
                      {/* Current IV indicator overlay */}
                      <div 
                        className="absolute text-xs font-bold text-blue-700 bg-blue-100 px-2 py-1 rounded border-2 border-blue-600 border-dashed"
                        style={{
                          bottom: `${Math.min((documentationData.modelDesign.segmentation.ivVisualizationCharts.ivStrength.value / 0.6) * 100, 95)}%`,
                          right: '10px',
                          transform: 'translateY(50%)'
                        }}
                      >
                        ← Current IV: {documentationData.modelDesign.segmentation.ivVisualizationCharts.ivStrength.value.toFixed(4)}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
            );
          })()}
        </div>
        </>
      ) : null}
          </>
        )}
      </CollapsibleSection>

      {/* FEATURE ENGINEERING/TRANSFORMATION Section */}
      <CollapsibleSection sectionNumber={6} sectionTitle="FEATURE ENGINEERING/TRANSFORMATION" defaultExpanded={false}>
        {() => (
          <>

        {documentationData.featureEngineering.transformedVariables.length > 0 ? (
          <div className="pl-6 space-y-4">
          {/* Understand the Transformations Section */}
          {documentationData.featureEngineering.writeup?.content && (
            <div className="space-y-3">
              <h5 className="text-md font-semibold text-gray-800">Understand the Transformations</h5>
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <EditableField
                  value={documentationData.featureEngineering.writeup.content}
                  onSave={(newValue) => {
                    updateFeatureEngineering({
                      writeup: {
                        content: newValue,
                        lastGenerated: documentationData.featureEngineering.writeup?.lastGenerated || null,
                      },
                    });
                  }}
                  multiline={true}
                />
        </div>
      </div>
    )}

          {/* Rows filter */}
          <div className="flex items-center justify-end space-x-2">
            <label htmlFor="fe-rowsToShow" className="text-sm text-gray-600">Rows to show:</label>
            <input
              id="fe-rowsToShow"
              type="number"
              min="1"
              max={documentationData.featureEngineering.transformedVariables.length}
              value={documentationData.featureEngineering.rowsToShow}
              onChange={(e) => {
                const value = parseInt(e.target.value);
                if (!isNaN(value) && value > 0) {
                  updateFeatureEngineering({
                    rowsToShow: value,
                  });
                }
              }}
              className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
            />
          </div>

          {/* Transformed Variables Table */}
          <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b-2 border-gray-300">
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">New Transformed Variable</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Var Type</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Variable definition</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Transformation method</th>
                </tr>
              </thead>
              <tbody>
                {documentationData.featureEngineering.transformedVariables
                  .slice(0, documentationData.featureEngineering.rowsToShow)
                  .map((variable, index) => (
                    <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                      <td className="px-4 py-2 text-gray-900 font-medium">{variable.new_variable_name}</td>
                      <td className="px-4 py-2 text-gray-800">{variable.var_type}</td>
                      <td className="px-4 py-2 text-gray-600">{variable.variable_definition || '-'}</td>
                      <td className="px-4 py-2 text-gray-600">
                        <span className="px-2 py-1 rounded text-xs bg-green-100 text-green-800">
                          {variable.transformation_methods}
                        </span>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
        ) : (
          <div className="pl-6">
            <p className="text-gray-700">You didn't perform Feature Engineering! Go to Feature Engineering page and transform your variables.</p>
          </div>
        )}
          </>
        )}
      </CollapsibleSection>

      {/* MODEL DEVELOPMENT Section */}
      <CollapsibleSection sectionNumber={7} sectionTitle="MODEL DEVELOPMENT" defaultExpanded={false}>
        {() => (
          <>

      <div className="pl-6 space-y-6">
        {modelDevelopmentPlaceholders.map((section) => (
          <div key={section.id} className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-lg font-bold text-gray-800">
                {section.id} {section.title}
              </h4>
              <span className="text-xs font-medium text-gray-600 bg-gray-100 border border-gray-200 px-3 py-1 rounded-full">
                Placeholder
              </span>
            </div>
            <p className="text-gray-600">{section.description}</p>

            {section.children.length > 0 && (
              <div className="border-l-2 border-gray-200 pl-6 space-y-4">
                {section.children.map((child) => (
                  <div
                    key={child.id}
                    className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <h5 className="text-md font-semibold text-gray-900">
                        {child.id} {child.title}
                      </h5>
                      <span className="text-xs font-medium text-blue-600">Coming soon</span>
                    </div>
                    <p className="text-sm text-gray-600">
                      {child.body}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {section.children.length === 0 && (
              <div className="bg-gray-50 border border-dashed border-gray-300 rounded-lg p-4">
                <p className="text-sm text-gray-600">
                  Detailed write-ups for {section.title} will appear here after you complete the Model Development agent.
                </p>
              </div>
            )}
          </div>
        ))}

        {/* 7.1 Model Selection */}
        <div className="space-y-4">
          <div className="space-y-1">
            <h4 className="text-lg font-bold text-gray-800">7.1 Model Selection</h4>
            <div className="text-sm text-blue-600">
              <p className="font-semibold">{modelSelectionData.metadata.algorithm}</p>
              <p>{modelSelectionData.metadata.optimizationMethod}</p>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
            <EditableField
              value={modelSelectionData.narrative || ''}
              onSave={(value) => updateModelSelection({ narrative: value })}
              multiline
            />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-gray-500">Iterations</p>
                <p className="font-semibold text-gray-900">{modelSelectionData.metadata.iterationCount || '-'}</p>
              </div>
              <div>
                <p className="text-gray-500">Models tested</p>
                <p className="font-semibold text-gray-900">{modelSelectionData.metadata.totalModelsTested || '-'}</p>
              </div>
              <div>
                <p className="text-gray-500">{modelSelectionData.metadata.scoreMetric}</p>
                <p className="font-semibold text-gray-900">
                  {modelSelectionData.metadata.bestScore
                    ? modelSelectionData.metadata.bestScore.toFixed(
                        modelSelectionData.metadata.scoreMetric === 'KS' ? 2 : 4
                      )
                    : '-'}
                </p>
              </div>
              <div>
                <p className="text-gray-500">Last updated</p>
                <p className="font-semibold text-gray-900">
                  {new Date(modelSelectionData.metadata.generatedAt).toLocaleDateString()}
                </p>
              </div>
            </div>
          </div>

          {/* 7.1.1 Final Set of Variables */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h5 className="text-md font-semibold text-gray-900">7.1.1 Final Set of Variables</h5>
              <span className="text-xs text-gray-600">
                Total retained: {modelSelectionData.finalVariables.totalCount}
              </span>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              {modelSelectionData.finalVariables.variableAnalysis && modelSelectionData.finalVariables.variableAnalysis.length > 0 ? (
                <div className="space-y-3">
                  {/* Rows filter */}
                  <div className="flex items-center justify-end space-x-2">
                    <label htmlFor="variableAnalysisRows" className="text-sm text-gray-600">Show</label>
                    <input
                      id="variableAnalysisRows"
                      type="number"
                      min="1"
                      max={modelSelectionData.finalVariables.variableAnalysis.length}
                      value={modelSelectionData.finalVariables.rowsToShow || modelSelectionData.finalVariables.variableAnalysis.length}
                      onChange={(e) => {
                        const value = parseInt(e.target.value);
                        if (!isNaN(value) && value > 0) {
                          updateModelSelection({
                            finalVariables: {
                              ...modelSelectionData.finalVariables,
                              rowsToShow: value,
                            },
                          });
                        }
                      }}
                      className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                    />
                    <span className="text-sm text-gray-600">rows</span>
                  </div>
                  
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead className="bg-gray-50 border-b-2 border-gray-300">
                        <tr>
                          <th className="px-4 py-3 text-left font-semibold text-gray-700">Variable Name</th>
                          <th className="px-4 py-3 text-right font-semibold text-gray-700">Correlation</th>
                          <th className="px-4 py-3 text-right font-semibold text-gray-700">VIF</th>
                          <th className="px-4 py-3 text-right font-semibold text-gray-700">IV</th>
                          <th className="px-4 py-3 text-left font-semibold text-gray-700">Interpretation</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {modelSelectionData.finalVariables.variableAnalysis
                          .slice(0, modelSelectionData.finalVariables.rowsToShow || modelSelectionData.finalVariables.variableAnalysis.length)
                          .map((stat, index) => {
                        const absCorr = Math.abs(stat.correlation || 0);
                        const corrColor = absCorr > 0.8 ? 'text-green-900 font-bold' : absCorr > 0.5 ? 'text-blue-900 font-medium' : absCorr < 0.1 ? 'text-orange-900' : 'text-gray-900';
                        const vifColor = stat.vif && stat.vif > 10 ? 'text-red-900 font-bold' : stat.vif && stat.vif > 5 ? 'text-orange-900 font-medium' : 'text-gray-900';
                        
                        return (
                          <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                            <td className="px-4 py-3 text-gray-900 font-medium">{stat.variable}</td>
                            <td className={`px-4 py-3 text-right ${corrColor}`}>
                              {stat.correlation !== null && stat.correlation !== undefined ? stat.correlation.toFixed(4) : 'N/A'}
                            </td>
                            <td className={`px-4 py-3 text-right ${vifColor}`}>
                              {stat.vif !== null && stat.vif !== undefined ? stat.vif.toFixed(2) : 'N/A'}
                            </td>
                            <td className="px-4 py-3 text-right text-purple-900">
                              {stat.iv !== null && stat.iv !== undefined ? Number(stat.iv).toFixed(4) : 'N/A'}
                            </td>
                            <td className="px-4 py-3 text-xs text-gray-600">
                              {stat.interpretation || 'Normal'}
                            </td>
                          </tr>
                        );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : hasVariableCategories ? (
                <div className="space-y-3">
                  {modelSelectionData.finalVariables.categories.map((category, index) => (
                  <div key={`${category.label}-${index}`} className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                    <div>
                      <p className="font-medium text-gray-900">{category.label}</p>
                      <p className="text-sm text-gray-600">{category.description}</p>
                    </div>
                    <div className="text-sm font-semibold text-blue-600">{category.count}</div>
                  </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-600 italic">
                  Sample text: The following 235 variables were selected in the final model (205 Premiers and 30 Clarity variables).
                  Attachments for the full list will appear once training outputs are available.
                </p>
              )}
              {modelSelectionData.finalVariables.attachmentNote && (
                <p className="text-xs text-gray-500 italic mt-3">{modelSelectionData.finalVariables.attachmentNote}</p>
              )}
            </div>
          </div>

          {/* 7.1.1.1 Bivariate Analysis */}
          {modelSelectionData.finalVariables.bivariateAnalysisCharts && 
           modelSelectionData.finalVariables.bivariateAnalysisCharts.charts.length > 0 && (
            <div className="space-y-4">
              <h5 className="text-md font-semibold text-gray-900">Bivariate Analysis</h5>
              
              {/* Filters */}
              <div className="flex items-center space-x-4">
                {/* Number of variables filter */}
                <div className="flex items-center space-x-2">
                  <label htmlFor="bivariateVariableCount" className="text-sm text-gray-600">Variables</label>
                  <input
                    id="bivariateVariableCount"
                    type="number"
                    min="1"
                    max={modelSelectionData.finalVariables.bivariateAnalysisCharts.charts.length}
                    value={modelSelectionData.finalVariables.bivariateAnalysisCharts.variableCount === 'all' 
                      ? modelSelectionData.finalVariables.bivariateAnalysisCharts.charts.length 
                      : modelSelectionData.finalVariables.bivariateAnalysisCharts.variableCount}
                    onChange={(e) => {
                      const value = parseInt(e.target.value);
                      if (!isNaN(value) && value > 0) {
                        updateModelSelection({
                          finalVariables: {
                            ...modelSelectionData.finalVariables,
                            bivariateAnalysisCharts: {
                              ...modelSelectionData.finalVariables.bivariateAnalysisCharts!,
                              variableCount: value,
                            },
                          },
                        });
                      }
                    }}
                    className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                  />
                </div>
              </div>

              {/* Charts Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {modelSelectionData.finalVariables.bivariateAnalysisCharts.charts
                  .slice(0, modelSelectionData.finalVariables.bivariateAnalysisCharts.variableCount === 'all' 
                    ? modelSelectionData.finalVariables.bivariateAnalysisCharts.charts.length 
                    : modelSelectionData.finalVariables.bivariateAnalysisCharts.variableCount)
                  .map((chartData, idx) => {
                    const { categories, bar_data, line_data } = chartData.visualization_data.data;
                    
                    // Prepare data for Chart.js combination chart
                    const chartDataConfig: any = {
                      labels: categories,
                      datasets: [
                        {
                          type: 'bar' as const,
                          label: bar_data.label || 'Total',
                          data: bar_data.values,
                          backgroundColor: 'rgba(34, 197, 94, 0.6)',
                          borderColor: 'rgba(34, 197, 94, 1)',
                          borderWidth: 1,
                          yAxisID: 'y-left',
                          order: 2,
                        },
                        {
                          type: 'line' as const,
                          label: line_data.label || 'Event Rate',
                          data: line_data.values,
                          borderColor: 'rgba(59, 130, 246, 1)',
                          backgroundColor: 'rgba(59, 130, 246, 0.1)',
                          borderWidth: 2,
                          pointBackgroundColor: 'rgba(59, 130, 246, 1)',
                          pointBorderColor: 'white',
                          pointBorderWidth: 2,
                          pointRadius: 4,
                          pointHoverRadius: 6,
                          yAxisID: 'y-right',
                          order: 1,
                          tension: 0.3,
                        }
                      ]
                    };

                    const chartOptions = {
                      responsive: true,
                      maintainAspectRatio: false,
                      interaction: {
                        mode: 'nearest' as const,
                        intersect: true,
                      },
                      plugins: {
                        title: {
                          display: true,
                          text: chartData.visualization_data.chart_title || `${chartData.variable_name} Analysis`,
                          font: {
                            size: 14,
                            weight: 'bold' as const,
                          },
                          color: '#374151',
                          padding: {
                            bottom: 20,
                          },
                        },
                        legend: {
                          display: true,
                          position: 'bottom' as const,
                          labels: {
                            usePointStyle: true,
                            padding: 15,
                            font: {
                              size: 12,
                            },
                          },
                        },
                        tooltip: {
                          backgroundColor: 'rgba(0, 0, 0, 0.8)',
                          titleColor: 'white',
                          bodyColor: 'white',
                          borderWidth: 1,
                          callbacks: {
                            label: function(context: any) {
                              const datasetLabel = context.dataset.label || '';
                              const value = context.parsed.y;
                              
                              if (context.datasetIndex === 0) {
                                return `${datasetLabel}: ${value.toFixed(4)}`;
                              } else {
                                return `${datasetLabel}: ${(value * 100).toFixed(4)}%`;
                              }
                            }
                          }
                        }
                      },
                      scales: {
                        x: {
                          grid: {
                            display: true,
                            color: 'rgba(0, 0, 0, 0.1)',
                          },
                          ticks: {
                            color: '#374151',
                            font: {
                              size: 11,
                              weight: 'bold' as const,
                            },
                            maxRotation: categories.length > 3 ? 45 : 0,
                            callback: function(_tickValue: any, index: number) {
                              const label = categories[index];
                              return label.length > 10 ? label.substring(0, 10) + '...' : label;
                            }
                          },
                          title: {
                            display: true,
                            text: chartData.variable_type === 'categorical' ? 'Category' : 'Bin Range (Decile)',
                            color: '#374151',
                            font: {
                              size: 12,
                              weight: 'bold' as const,
                            },
                          },
                        },
                        'y-left': {
                          type: 'linear' as const,
                          display: true,
                          position: 'left' as const,
                          grid: {
                            display: true,
                            color: 'rgba(0, 0, 0, 0.1)',
                          },
                          ticks: {
                            color: '#374151',
                            font: {
                              size: 11,
                              weight: 'bold' as const,
                            },
                            callback: function(tickValue: any) {
                              return tickValue.toLocaleString();
                            }
                          },
                          title: {
                            display: true,
                            text: 'Total',
                            color: '#374151',
                            font: {
                              size: 12,
                              weight: 'bold' as const,
                            },
                          },
                        },
                        'y-right': {
                          type: 'linear' as const,
                          display: true,
                          position: 'right' as const,
                          grid: {
                            drawOnChartArea: false,
                          },
                          ticks: {
                            color: '#374151',
                            font: {
                              size: 11,
                              weight: 'bold' as const,
                            },
                            callback: function(tickValue: any) {
                              return (tickValue * 100).toFixed(1) + '%';
                            }
                          },
                          title: {
                            display: true,
                            text: 'Event Rate',
                            color: '#374151',
                            font: {
                              size: 12,
                              weight: 'bold' as const,
                            },
                          },
                        },
                      },
                    };

                    return (
                      <div key={idx} className="border border-gray-200 rounded-lg p-4 bg-white">
                        <div className="h-80">
                          <MemoizedBar data={chartDataConfig} options={chartOptions} />
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* 7.1.2 Model parameters */}
          <div className="space-y-3">
            <h5 className="text-md font-semibold text-gray-900">7.1.2 Model parameters</h5>
            <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
              {hasHyperparameters && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  {modelSelectionData.hyperparameters.summaryList.map((param) => (
                    <div key={param.name} className="flex items-center justify-between border-b border-gray-100 pb-2">
                      <span className="text-gray-600">{param.name}</span>
                      <span className="font-semibold text-gray-900">{String(param.value)}</span>
                    </div>
                  ))}
                </div>
              )}

            </div>
          </div>
        </div>
        </div>
          </>
        )}
      </CollapsibleSection>

      {/* MODEL PERFORMANCE Section */}
      <CollapsibleSection sectionNumber={8} sectionTitle="MODEL PERFORMANCE" defaultExpanded={false}>
        {() => (
          <>

        {/* 8.1 Features */}
        <div className="space-y-4">
          <h4 className="text-lg font-bold text-gray-800">8.1 Features</h4>
          
          {/* Feature Count Text */}
          <p className="text-gray-700 pl-6">
            There are total <span className="font-semibold text-blue-600">{documentationData.modelPerformance.features.totalCount}</span> features being selected in the final model.
          </p>

          {/* 8.1.1 Top Features */}
          <div className="space-y-4">
            <div className="flex items-center justify-between pl-6">
              <h5 className="text-md font-bold text-gray-800">8.1.1 Top Features</h5>
              {/* Input to change topN */}
              <div className="flex items-center space-x-2">
                <label htmlFor="topN" className="text-sm text-gray-600">Show top</label>
                <input
                  id="topN"
                  type="number"
                  min="1"
                  max={documentationData.modelPerformance.features.totalCount}
                  value={documentationData.modelPerformance.features.topN}
                  onChange={(e) => {
                    const value = parseInt(e.target.value);
                    if (!isNaN(value) && value > 0) {
                      updateModelPerformance({
                        features: {
                          ...documentationData.modelPerformance.features,
                          topN: value,
                        },
                      });
                    }
                  }}
                  className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                />
                <span className="text-sm text-gray-600">features</span>
              </div>
            </div>

            {/* Top Features Table */}
            {documentationData.modelPerformance.features.topFeatures.length > 0 ? (
              <div className="pl-6 overflow-x-auto">
                <table className="min-w-full border border-gray-300">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Feature</th>
                      <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Importance</th>
                      {documentationData.modelPerformance.features.topFeatures.some(f => f.description) && (
                        <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Description</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {documentationData.modelPerformance.features.topFeatures
                      .slice(0, documentationData.modelPerformance.features.topN)
                      .map((feature, index) => (
                        <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">{feature.featureName}</td>
                          <td className="px-4 py-2 border-b border-gray-200 text-gray-900">
                            {feature.importance >= 0 ? '+' : ''}{feature.importance.toFixed(4)}
                          </td>
                          {documentationData.modelPerformance.features.topFeatures.some(f => f.description) && (
                            <td className="px-4 py-2 border-b border-gray-200 text-gray-700">{feature.description || '-'}</td>
                          )}
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-gray-500 italic pl-6">No feature importance data available</p>
            )}

            {/* Feature Category Distribution Chart */}
            {Object.keys(documentationData.modelPerformance.features.categoryDistribution).length > 0 && (
              <div className="pl-6 space-y-4">
                <h5 className="text-md font-semibold text-gray-800">Feature Category Distribution</h5>
                <div className="max-w-3xl">
                  <Bar
                    data={{
                      labels: Object.keys(documentationData.modelPerformance.features.categoryDistribution),
                      datasets: [
                        {
                          label: 'Number of Features',
                          data: Object.values(documentationData.modelPerformance.features.categoryDistribution),
                          backgroundColor: Object.keys(documentationData.modelPerformance.features.categoryDistribution).map(
                            category => documentationData.modelPerformance.features.categoryColors[category] || '#3b82f6'
                          ),
                          borderColor: Object.keys(documentationData.modelPerformance.features.categoryDistribution).map(
                            category => documentationData.modelPerformance.features.categoryColors[category] || '#2563eb'
                          ),
                          borderWidth: 1,
                        },
                      ],
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: true,
                      plugins: {
                        legend: {
                          display: false,
                        },
                        title: {
                          display: false,
                        },
                      },
                      scales: {
                        x: {
                          ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                          },
                        },
                        y: {
                          beginAtZero: true,
                          ticks: {
                            stepSize: 1,
                          },
                        },
                      },
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 8.2 ROC Curve Comparison */}
        {documentationData.modelPerformance.rocCurves && (
          <div className="space-y-4">
            <h4 className="text-lg font-bold text-gray-800">8.2 ROC Curve Comparison</h4>
            
            <div className="pl-6 space-y-6">
              {/* 8.2.1 Train */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h5 className="text-md font-bold text-gray-800">8.2.1 Train</h5>
                </div>
                {documentationData.modelPerformance.rocCurves.train && documentationData.modelPerformance.rocCurves.train.length > 0 ? (
                  <MemoizedROCCurveComparison
                    models={documentationData.modelPerformance.rocCurves.train as any}
                    title="ROC Curve Comparison (Train)"
                  />
                ) : (
                  <div className="bg-white rounded-lg p-6 border border-gray-200">
                    <p className="text-gray-500 text-center">No train ROC curve data available</p>
                  </div>
                )}
      </div>

              {/* 8.2.2 Test */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h5 className="text-md font-bold text-gray-800">8.2.2 Test</h5>
                </div>
                {documentationData.modelPerformance.rocCurves.test && documentationData.modelPerformance.rocCurves.test.length > 0 ? (
                  <MemoizedROCCurveComparison
                    models={documentationData.modelPerformance.rocCurves.test as any}
                    title="ROC Curve Comparison (Test)"
                  />
                ) : (
                  <div className="bg-white rounded-lg p-6 border border-gray-200">
                    <p className="text-gray-500 text-center">No test ROC curve data available</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 8.3 Confusion Matrix Comparison */}
        {documentationData.modelPerformance.confusionMatrices && documentationData.modelPerformance.confusionMatrices.length > 0 && (
          <div className="space-y-4">
            <h4 className="text-lg font-bold text-gray-800">8.3 Confusion Matrix Comparison</h4>
            
            <div className="pl-6 space-y-6">
              <MemoizedConfusionMatrixComparison
                models={documentationData.modelPerformance.confusionMatrices}
                title="Confusion Matrix Comparison"
              />
            </div>
          </div>
        )}

        {/* 8.4 Performance Radar Chart */}
        {documentationData.modelPerformance.radarCharts && (
          <div className="space-y-4">
            <h4 className="text-lg font-bold text-gray-800">8.4 Performance Radar Chart</h4>
            
            <div className="pl-6 space-y-6">
              {/* 8.4.1 Train */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h5 className="text-md font-bold text-gray-800">8.4.1 Train</h5>
                </div>
                {documentationData.modelPerformance.radarCharts.train && documentationData.modelPerformance.radarCharts.train.length > 0 ? (
                  <MemoizedPerformanceRadarChart
                    models={documentationData.modelPerformance.radarCharts.train}
                    title="Performance Radar Chart (Train)"
                  />
                ) : (
                  <div className="bg-white rounded-lg p-6 border border-gray-200">
                    <p className="text-gray-500 text-center">No train radar chart data available</p>
                  </div>
                )}
              </div>

              {/* 8.4.2 Test */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h5 className="text-md font-bold text-gray-800">8.4.2 Test</h5>
                </div>
                {documentationData.modelPerformance.radarCharts.test && documentationData.modelPerformance.radarCharts.test.length > 0 ? (
                  <MemoizedPerformanceRadarChart
                    models={documentationData.modelPerformance.radarCharts.test}
                    title="Performance Radar Chart (Test)"
                  />
                ) : (
                  <div className="bg-white rounded-lg p-6 border border-gray-200">
                    <p className="text-gray-500 text-center">No test radar chart data available</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 8.5 Monotonicity */}
        {documentationData.modelPerformance.monotonicity && documentationData.modelPerformance.monotonicity.length > 0 && (
          <div className="space-y-4">
            <h4 className="text-lg font-bold text-gray-800">8.5 Monotonicity</h4>
            
            <div className="pl-6 space-y-6">
              {/* Summary Table and Writeup */}
              <div className="space-y-4">
                {/* Summary Table */}
                <div className="overflow-x-auto">
                  <table className="min-w-full border border-gray-300 text-sm">
                    <thead className="bg-gray-100">
                      <tr>
                        <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Model</th>
                        <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Monotonicity Score</th>
                        <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">KS Statistic</th>
                        <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Lift</th>
                        <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">AUC/Gini</th>
                        <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">PSI</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documentationData.modelPerformance.monotonicity.map((mono) => {
                        const psiValue = mono.psi?.value ?? (typeof mono.psi === 'number' ? mono.psi : null);
                        return (
                          <tr key={mono.modelId}>
                            <td className="border border-gray-300 px-3 py-2 text-gray-900 font-medium">{mono.modelName}</td>
                            <td className="border border-gray-300 px-3 py-2 text-gray-900">{mono.monotonicityScore.toFixed(2)}%</td>
                            <td className="border border-gray-300 px-3 py-2 text-gray-900">{mono.ksStatistic.toFixed(3)}</td>
                            <td className="border border-gray-300 px-3 py-2 text-gray-900">
                              {mono.liftTopDecile !== null ? `${mono.liftTopDecile.toFixed(2)}x` : 'N/A'}
                            </td>
                            <td className="border border-gray-300 px-3 py-2 text-gray-900">AUC {mono.auc.toFixed(3)} / Gini {mono.gini.toFixed(3)}</td>
                            <td className="border border-gray-300 px-3 py-2 text-gray-900">
                              {psiValue !== null ? psiValue.toFixed(4) : 'N/A'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                
                {/* LLM Writeup */}
                {documentationData.modelPerformance.monotonicitySummary?.writeup && (
                  <div className="space-y-2">
                    <EditableField
                      value={documentationData.modelPerformance.monotonicitySummary.writeup}
                      onSave={(value) => updateModelPerformance({ 
                        monotonicitySummary: { 
                          ...documentationData.modelPerformance.monotonicitySummary,
                          writeup: value 
                        } 
                      })}
                      multiline
                    />
                    {documentationData.modelPerformance.monotonicitySummary.lastGenerated && (
                      <p className="text-xs text-gray-500 italic">
                        Generated on: {new Date(documentationData.modelPerformance.monotonicitySummary.lastGenerated).toLocaleString()}
                      </p>
                    )}
                  </div>
                )}
              </div>
              
              {/* Individual Model Sections */}
              <div className="space-y-8">
              {documentationData.modelPerformance.monotonicity.map((mono, index) => (
                <div key={mono.modelId} className="space-y-4 border-b border-gray-200 pb-6 last:border-b-0">
                  <h5 className="text-md font-bold text-gray-800">8.5.{index + 1} {mono.modelName}</h5>
                  
                  {/* Monotonicity Metrics Table */}
                  <div className="overflow-x-auto">
                    <table className="min-w-full border border-gray-300 text-sm">
                      <thead className="bg-gray-100">
                        <tr>
                          <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Monotonicity Score</th>
                          <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">KS Statistic</th>
                          <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Lift (Top Decile)</th>
                          <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">AUC / Gini</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td className="border border-gray-300 px-3 py-2 text-gray-900">{mono.monotonicityScore.toFixed(2)}%</td>
                          <td className="border border-gray-300 px-3 py-2 text-gray-900">{mono.ksStatistic.toFixed(3)} (Threshold: {mono.ksThreshold.toFixed(3)})</td>
                          <td className="border border-gray-300 px-3 py-2 text-gray-900">
                            {mono.liftTopDecile !== null ? `${mono.liftTopDecile.toFixed(2)}x` : 'N/A'} 
                            {mono.liftTopDecile !== null && ` (Overall bad rate: ${(mono.overallBadRate * 100).toFixed(2)}%)`}
                          </td>
                          <td className="border border-gray-300 px-3 py-2 text-gray-900">AUC {mono.auc.toFixed(3)} · Gini {mono.gini.toFixed(3)}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  
                  <div className="space-y-3">
                    
                    {/* PSI Section */}
                    {mono.psi && (
                      <div className="space-y-3">
                        <div className="flex items-start gap-2">
                          <span className="text-sm font-semibold text-gray-700 min-w-[200px]">Population Stability Index (PSI):</span>
                          <div className="flex-1">
                            <table className="min-w-full border border-gray-300 text-sm">
                              <thead className="bg-gray-100">
                                <tr>
                                  <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">PSI Value</th>
                                  <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Status</th>
                                  <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Interpretation</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr>
                                  <td className="border border-gray-300 px-3 py-2 text-gray-900">{mono.psi.value.toFixed(4)}</td>
                                  <td className="border border-gray-300 px-3 py-2">
                                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                                      mono.psi.status === 'Stable' ? 'bg-emerald-100 text-emerald-700' :
                                      mono.psi.status === 'Moderate' ? 'bg-amber-100 text-amber-700' :
                                      'bg-red-100 text-red-700'
                                    }`}>
                                      {mono.psi.status}
                                    </span>
                                  </td>
                                  <td className="border border-gray-300 px-3 py-2 text-gray-900">{mono.psi.interpretation}</td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {/* CSI Section */}
                    {mono.csi && mono.csi.length > 0 && (
                      <div className="space-y-3">
                        <div className="flex items-start gap-2">
                          <span className="text-sm font-semibold text-gray-700 min-w-[200px]">Characteristic Stability Index (CSI):</span>
                          <div className="flex-1">
                            <table className="min-w-full border border-gray-300 text-sm">
                              <thead className="bg-gray-100">
                                <tr>
                                  <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Variable Name</th>
                                  <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">CSI Value</th>
                                  <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {mono.csi.map((csiRow, csiIdx) => (
                                  <tr key={csiIdx}>
                                    <td className="border border-gray-300 px-3 py-2 text-gray-900">{csiRow.variable}</td>
                                    <td className="border border-gray-300 px-3 py-2 text-gray-900">{csiRow.csiValue.toFixed(4)}</td>
                                    <td className="border border-gray-300 px-3 py-2">
                                      <span className={`px-2 py-1 rounded text-xs font-semibold ${
                                        csiRow.status === 'Stable' ? 'bg-emerald-100 text-emerald-700' :
                                        csiRow.status === 'Moderate' ? 'bg-amber-100 text-amber-700' :
                                        'bg-red-100 text-red-700'
                                      }`}>
                                        {csiRow.status}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {mono.decileProgressionWriteup && (
                      <div className="flex items-start gap-2">
                        <span className="text-sm font-semibold text-gray-700 min-w-[200px]">Understand the Decile Progression:</span>
                        <div className="flex-1 bg-gray-50 border border-gray-200 rounded-lg p-4">
                          <EditableField
                            value={mono.decileProgressionWriteup}
                            onSave={(newValue) => {
                              const updatedMonotonicity = documentationData.modelPerformance.monotonicity.map((m) => 
                                m.modelId === mono.modelId 
                                  ? { ...m, decileProgressionWriteup: newValue }
                                  : m
                              );
                              updateModelPerformance({
                                monotonicity: updatedMonotonicity,
                              });
                            }}
                            multiline={true}
                          />
                        </div>
                      </div>
                    )}
                    
                    {/* Decile Table */}
                    {mono.deciles && mono.deciles.length > 0 && (
                      <div className="space-y-2">
                        <div className="overflow-x-auto">
                          <table className="min-w-full border border-gray-300 text-sm">
                            <thead className="bg-gray-100">
                              <tr>
                                <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Decile</th>
                                <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Count</th>
                                <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Bads</th>
                                <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Goods</th>
                                <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Bad Rate</th>
                                <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Avg Score</th>
                                <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Lift</th>
                                <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">Cum Bad Rate</th>
                              </tr>
                            </thead>
                            <tbody>
                              {mono.deciles.map((decile: any, decileIdx: number) => (
                                <tr key={decileIdx}>
                                  <td className="border border-gray-300 px-3 py-2 text-gray-900 font-medium">{decile.Decile ?? decileIdx + 1}</td>
                                  <td className="border border-gray-300 px-3 py-2 text-gray-900">{decile.Count ?? 0}</td>
                                  <td className="border border-gray-300 px-3 py-2 text-gray-900">{decile.Bads ?? 0}</td>
                                  <td className="border border-gray-300 px-3 py-2 text-gray-900">{decile.Goods ?? 0}</td>
                                  <td className="border border-gray-300 px-3 py-2 text-gray-900">
                                    {decile.Bad_Rate !== undefined ? `${(decile.Bad_Rate * 100).toFixed(2)}%` : 'N/A'}
                                  </td>
                                  <td className="border border-gray-300 px-3 py-2 text-gray-900">
                                    {decile.Avg_Score !== undefined ? decile.Avg_Score.toFixed(3) : 'N/A'}
                                  </td>
                                  <td className="border border-gray-300 px-3 py-2 text-gray-900">
                                    {decile.Lift !== undefined ? `${decile.Lift.toFixed(2)}x` : 'N/A'}
                                  </td>
                                  <td className="border border-gray-300 px-3 py-2 text-gray-900">
                                    {decile.Cum_Bad_Rate !== undefined ? `${(decile.Cum_Bad_Rate * 100).toFixed(2)}%` : 'N/A'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              </div>
            </div>
          </div>
        )}

        {/* 8.6 Granular Accuracy */}
        {documentationData.modelPerformance.granularAccuracy && documentationData.modelPerformance.granularAccuracy.variables.length > 0 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-lg font-bold text-gray-800">8.6 Granular Accuracy</h4>
              {/* Variables filter */}
              <div className="flex items-center space-x-2">
                <label htmlFor="granularAccuracyVariables" className="text-sm text-gray-600">Show</label>
                <input
                  id="granularAccuracyVariables"
                  type="number"
                  min="1"
                  max={documentationData.modelPerformance.granularAccuracy.variables.length}
                  value={documentationData.modelPerformance.granularAccuracy.variablesToShow}
                  onChange={(e) => {
                    const value = parseInt(e.target.value);
                    if (!isNaN(value) && value > 0) {
                      updateModelPerformance({
                        granularAccuracy: {
                          ...documentationData.modelPerformance.granularAccuracy!,
                          variablesToShow: value,
                        },
                      });
                    }
                  }}
                  className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                />
                <span className="text-sm text-gray-600">variables</span>
              </div>
            </div>

            <div className="pl-6 space-y-8">
              {documentationData.modelPerformance.granularAccuracy.variables
                .slice(0, documentationData.modelPerformance.granularAccuracy.variablesToShow)
                .map((variable, varIndex) => (
                  <div key={varIndex} className="space-y-3">
                    <h5 className="text-md font-bold text-gray-800">Variable: {variable.variableName}</h5>
                    
                    <div className="overflow-x-auto">
                      <table className="min-w-full border border-gray-300">
                        <thead className="bg-gray-100">
                          <tr>
                            <th className="px-4 py-2 text-left border-b border-gray-300 font-semibold text-gray-700">Segment</th>
                            <th className="px-4 py-2 text-center border-b border-gray-300 font-semibold text-gray-700">Accuracy</th>
                            <th className="px-4 py-2 text-center border-b border-gray-300 font-semibold text-gray-700">Precision</th>
                            <th className="px-4 py-2 text-center border-b border-gray-300 font-semibold text-gray-700">Recall</th>
                            <th className="px-4 py-2 text-center border-b border-gray-300 font-semibold text-gray-700">F1 Score</th>
                          </tr>
                        </thead>
                        <tbody>
                          {variable.segments.map((segment, segIndex) => (
                            <tr key={segIndex} className={segIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                              <td className="px-4 py-2 border-b border-gray-200 text-gray-900 font-medium">{segment.segment}</td>
                              <td className="px-4 py-2 border-b border-gray-200 text-gray-900 text-center">{(segment.accuracy * 100).toFixed(2)}%</td>
                              <td className="px-4 py-2 border-b border-gray-200 text-gray-900 text-center">{segment.precision.toFixed(4)}</td>
                              <td className="px-4 py-2 border-b border-gray-200 text-gray-900 text-center">{segment.recall.toFixed(4)}</td>
                              <td className="px-4 py-2 border-b border-gray-200 text-gray-900 text-center">{segment.f1Score.toFixed(4)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}
          </>
        )}
      </CollapsibleSection>

      {/* 9. AI EXPLAINABILITY Section */}
      <CollapsibleSection sectionNumber={9} sectionTitle="AI EXPLAINABILITY" defaultExpanded={false}>
        {() => (
          <>

        {documentationData.modelPerformance.explainability ? (
          <div className="pl-6 space-y-6">
            {/* 9.1 Understand AI Explainability */}
            {documentationData.modelPerformance.explainability?.writeup && (
              <div className="space-y-4">
                <h4 className="text-lg font-bold text-gray-800">9.1 Understand AI Explainability</h4>
                <div className="pl-6 bg-white rounded-lg p-4 border border-gray-200">
                  <EditableField
                    value={documentationData.modelPerformance.explainability.writeup.content}
                    onSave={(newValue) => {
                      updateModelPerformance({
                        explainability: {
                          ...documentationData.modelPerformance.explainability,
                          writeup: {
                            ...documentationData.modelPerformance.explainability.writeup,
                            content: newValue,
                          },
                        },
                      });
                    }}
                    multiline={true}
                  />
                </div>
              </div>
            )}

            {/* 9.2 SHAP */}
            {documentationData.modelPerformance.explainability.shap && (
              <div className="space-y-4">
                <h4 className="text-lg font-bold text-gray-800">9.2 SHAP</h4>

                {/* 9.2.1 Beeswarm Plot and 9.2.2 Waterfall - Side by Side */}
                <div className="space-y-4">
                  {/* Side by side layout matching AI Explainability page */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Beeswarm Plot */}
                    <div className="bg-gray-50 rounded-lg p-6 border border-gray-200">
                      <h5 className="text-md font-bold text-gray-800 mb-2">9.2.1 Beeswarm Plot</h5>
                      {/* Beeswarm feature count filter */}
                      {documentationData.modelPerformance.explainability.shap.beeswarm && (
                        <div className="flex items-center space-x-2 mb-4">
                          <label htmlFor="beeswarmFeatureCount" className="text-sm text-gray-600">Beeswarm:</label>
                          <select
                            id="beeswarmFeatureCount"
                            value={documentationData.modelPerformance.explainability.shap.beeswarm.featureCount}
                            onChange={(e) => {
                              const value = e.target.value === 'all' ? 'all' : parseInt(e.target.value);
                              if (value === 'all' || (!isNaN(value as number) && value > 0)) {
                                updateModelPerformance({
                                  explainability: {
                                    ...documentationData.modelPerformance.explainability!,
                                    shap: {
                                      ...documentationData.modelPerformance.explainability!.shap!,
                                      beeswarm: {
                                        ...documentationData.modelPerformance.explainability!.shap!.beeswarm!,
                                        featureCount: value,
                                      },
                                    },
                                  },
                                });
                              }
                            }}
                            className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                          >
                            <option value="5">5</option>
                            <option value="10">10</option>
                            <option value="20">20</option>
                            <option value="all">All</option>
                          </select>
                        </div>
                      )}
                      <h3 className="text-base font-semibold text-gray-900 mb-2 text-center">SHAP Beeswarm Plot</h3>
                      <p className="text-xs text-gray-600 text-center mb-4">
                        Each dot represents a sample. Horizontal position = SHAP value, Color = feature value
                      </p>
                      {documentationData.modelPerformance.explainability.shap.beeswarm && documentationData.modelPerformance.explainability.shap.beeswarm.data.length > 0 ? (
                        <div className="relative">
                          {(() => {
                            const filteredData = documentationData.modelPerformance.explainability.shap.beeswarm.featureCount === 'all'
                              ? documentationData.modelPerformance.explainability.shap.beeswarm.data
                              : documentationData.modelPerformance.explainability.shap.beeswarm.data.slice(0, documentationData.modelPerformance.explainability.shap.beeswarm.featureCount as number);
                            
                            // Calculate global plot range
                            const allShapValues: number[] = [];
                            filteredData.forEach(item => {
                              if (item.values && Array.isArray(item.values)) {
                                allShapValues.push(...item.values);
                              }
                            });
                            
                            const globalMinShap = allShapValues.length > 0 ? allShapValues.reduce((min, val) => Math.min(min, val), allShapValues[0]) : 0;
                            const globalMaxShap = allShapValues.length > 0 ? allShapValues.reduce((max, val) => Math.max(max, val), allShapValues[0]) : 0;
                            const globalMaxAbs = Math.max(Math.abs(globalMinShap), Math.abs(globalMaxShap));
                            const padding = globalMaxAbs * 0.1;
                            const globalPlotMin = -globalMaxAbs - padding;
                            const globalPlotMax = globalMaxAbs + padding;
                            
                            return (
                              <div className="relative w-full">
                                <div className="w-full flex flex-col gap-3 py-2 pb-2">
                                  {filteredData.map((item, featureIdx) => (
                                    <SHAPBeeswarmPlotCanvas
                                      key={featureIdx}
                                      shapData={{
                                        values: item.values || [],
                                        feature_values: item.feature_values || [],
                                        original_feature_values: item.original_feature_values,
                                        mean_abs: item.mean_abs,
                                        original_feature_name: item.original_feature_name
                                      }}
                                      featureName={item.featureName || `Feature ${featureIdx}`}
                                      height={50}
                                      globalPlotMin={globalPlotMin}
                                      globalPlotMax={globalPlotMax}
                                    />
                                  ))}
                                </div>
                                
                                {/* Shared X-axis with zero label */}
                                <div className="mt-4 relative">
                                  <div className="pt-2">
                                    <div className="relative flex justify-between items-center border-t border-gray-300 pt-2" style={{ paddingLeft: '9rem', paddingRight: '7rem' }}>
                                      <span className="text-xs text-gray-600">{globalPlotMin.toFixed(3)}</span>
                                      <div 
                                        className="absolute flex flex-col items-center"
                                        style={{
                                          left: 'calc(9rem + 0.75rem + ((100% - 9rem - 0.75rem - 7rem - 0.75rem) / 2))',
                                          transform: 'translateX(-50%)',
                                          top: '-0.25rem'
                                        }}
                                      >
                                        <span className="text-xs font-semibold text-black">0</span>
                                        <span className="text-xs font-medium text-gray-700 mt-1">SHAP value</span>
                                      </div>
                                      <span className="text-xs text-gray-600">{globalPlotMax.toFixed(3)}</span>
                                    </div>
                                    <div className="flex justify-between items-center mt-1" style={{ paddingLeft: '9rem', paddingRight: '6rem' }}>
                                      <span className="text-xs text-gray-400">Negative</span>
                                      <span className="text-xs text-gray-400">Positive</span>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            );
                          })()}
                        </div>
                      ) : (
                        <div className="text-center text-gray-500 py-8 space-y-2">
                          <div>No SHAP beeswarm data available</div>
                        </div>
                      )}
                      <div className="mt-4 pt-3 border-t border-gray-300">
                        <div className="text-sm text-gray-700 font-medium mb-2 text-center">SHAP value (impact on model output)</div>
                        <div className="flex flex-col items-center gap-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-600">Low</span>
                            <div 
                              className="w-40 h-4 rounded shadow-sm" 
                              style={{ 
                                background: 'linear-gradient(to right, #3b82f6 0%, #ffffff 50%, #ef4444 100%)',
                                border: '1px solid #e5e7eb'
                              }}
                            ></div>
                            <span className="text-xs text-gray-600">High</span>
                          </div>
                          <span className="text-xs text-gray-500">Feature value (hover over dots for details)</span>
                        </div>
                      </div>
                    </div>

                    {/* Waterfall Plot */}
                    <div className="bg-gray-50 rounded-lg p-6 border border-gray-200">
                      <h5 className="text-md font-bold text-gray-800 mb-2">9.2.2 Waterfall</h5>
                      {/* Waterfall feature count filter */}
                      {documentationData.modelPerformance.explainability.shap.waterfall && (
                        <div className="flex items-center space-x-2 mb-4">
                          <label htmlFor="waterfallFeatureCount" className="text-sm text-gray-600">Waterfall:</label>
                          <select
                            id="waterfallFeatureCount"
                            value={documentationData.modelPerformance.explainability.shap.waterfall.featureCount}
                            onChange={(e) => {
                              const value = e.target.value === 'all' ? 'all' : parseInt(e.target.value);
                              if (value === 'all' || (!isNaN(value as number) && value > 0)) {
                                updateModelPerformance({
                                  explainability: {
                                    ...documentationData.modelPerformance.explainability!,
                                    shap: {
                                      ...documentationData.modelPerformance.explainability!.shap!,
                                      waterfall: {
                                        ...documentationData.modelPerformance.explainability!.shap!.waterfall!,
                                        featureCount: value,
                                      },
                                    },
                                  },
                                });
                              }
                            }}
                            className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                          >
                            <option value="5">5</option>
                            <option value="10">10</option>
                            <option value="20">20</option>
                            <option value="all">All</option>
                          </select>
                        </div>
                      )}
                      <h3 className="text-base font-semibold text-gray-900 mb-3">SHAP Waterfall</h3>
                      {documentationData.modelPerformance.explainability.shap.waterfall && documentationData.modelPerformance.explainability.shap.waterfall.data.length > 0 ? (
                        <div className="pb-2">
                          <SHAPWaterfallPlot
                            waterfallData={
                              documentationData.modelPerformance.explainability.shap.waterfall.featureCount === 'all'
                                ? documentationData.modelPerformance.explainability.shap.waterfall.data
                                : documentationData.modelPerformance.explainability.shap.waterfall.data.slice(0, documentationData.modelPerformance.explainability.shap.waterfall.featureCount as number)
                            }
                            baseValue={documentationData.modelPerformance.explainability.shap.waterfall.baseValue}
                            modelColor="#3b82f6"
                          />
                        </div>
                      ) : (
                        <div className="text-center text-gray-500 py-8 space-y-2">
                          <div>No waterfall data available</div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 9.3 PDP/ICE Lines */}
            {documentationData.modelPerformance.explainability.pdp && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-lg font-bold text-gray-800">9.3 PDP/ICE Lines</h4>
                  <div className="flex items-center space-x-4">
                    {/* Feature count filter */}
                    <div className="flex items-center space-x-2">
                      <label htmlFor="pdpFeatureCount" className="text-sm text-gray-600">Features</label>
                      <input
                        id="pdpFeatureCount"
                        type="number"
                        min="1"
                        value={documentationData.modelPerformance.explainability.pdp.featureCount === 'all' ? '' : documentationData.modelPerformance.explainability.pdp.featureCount}
                        onChange={(e) => {
                          const value = e.target.value === '' ? 'all' : (parseInt(e.target.value) || 'all');
                          if (value === 'all' || (!isNaN(value as number) && value > 0)) {
                            updateModelPerformance({
                              explainability: {
                                ...documentationData.modelPerformance.explainability!,
                                pdp: {
                                  ...documentationData.modelPerformance.explainability!.pdp!,
                                  featureCount: value,
                                },
                              },
                            });
                          }
                        }}
                        className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                        placeholder="All"
                      />
                    </div>
                    {/* ICE Lines filter */}
                    <div className="flex items-center space-x-2">
                      <label htmlFor="pdpMaxIceLines" className="text-sm text-gray-600">ICE Lines</label>
                      <input
                        id="pdpMaxIceLines"
                        type="number"
                        min="1"
                        max="1000"
                        value={documentationData.modelPerformance.explainability.pdp.maxIceLines}
                        onChange={(e) => {
                          const value = parseInt(e.target.value);
                          if (!isNaN(value) && value > 0) {
                            updateModelPerformance({
                              explainability: {
                                ...documentationData.modelPerformance.explainability!,
                                pdp: {
                                  ...documentationData.modelPerformance.explainability!.pdp!,
                                  maxIceLines: value,
                                },
                              },
                            });
                          }
                        }}
                        className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                      />
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  {documentationData.modelPerformance.explainability.pdp && documentationData.modelPerformance.explainability.pdp.data.length > 0 ? (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {(() => {
                        const pdpSection = documentationData.modelPerformance.explainability.pdp!;
                        const filteredData = pdpSection.featureCount === 'all'
                          ? pdpSection.data
                          : pdpSection.data.slice(0, pdpSection.featureCount as number);

                        return filteredData.map((pdpData, idx) => {
                          // Ensure values are valid
                          const validValues = Array.isArray(pdpData.values) && pdpData.values.length > 0
                            ? pdpData.values.filter((v: any) => v && typeof v.x === 'number' && typeof v.y === 'number')
                            : [];
                          
                          const validIceLines = Array.isArray(pdpData.ice_lines) ? pdpData.ice_lines : [];
                          
                          if (validValues.length === 0) {
                            return null;
                          }

                          const featureName = pdpData.feature_name || 'Unknown Feature';
                          const displayName = featureName.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());

                          // Calculate ranges for axis labels
                          const allYValues = validValues.map(v => v.y);
                          const allIceYValues = validIceLines.slice(0, pdpSection.maxIceLines).flat().concat(allYValues);
                          const minY = allYValues.length > 0 ? allYValues.reduce((min, val) => Math.min(min, val), allYValues[0]) : 0;
                          const maxY = allYValues.length > 0 ? allYValues.reduce((max, val) => Math.max(max, val), allYValues[0]) : 0;
                          const iceMinY = allIceYValues.length > 0 ? allIceYValues.reduce((min, val) => Math.min(min, val), allIceYValues[0]) : minY;
                          const iceMaxY = allIceYValues.length > 0 ? allIceYValues.reduce((max, val) => Math.max(max, val), allIceYValues[0]) : maxY;
                          const iceRangeY = iceMaxY - iceMinY || 0.1;
                          const paddedMinY = iceMinY - iceRangeY * 0.05;
                          const paddedMaxY = iceMaxY + iceRangeY * 0.05;

                          const minX = validValues[0].x;
                          const maxX = validValues[validValues.length - 1].x;
                          const rangeX = maxX - minX || 1;

                          const totalIceLines = validIceLines.length;
                          const displayIceLines = validIceLines.slice(0, pdpSection.maxIceLines);

                          return (
                            <div key={idx} className="border border-gray-200 rounded-lg p-4 bg-white">
                              <h4 className="text-sm font-semibold text-gray-800 mb-3">
                                {displayName}
                              </h4>
                              <div className="relative h-64 bg-gray-50 rounded-lg" style={{ paddingLeft: '56px', paddingRight: '16px', paddingTop: '16px', paddingBottom: '56px' }}>
                                <PDPICEPlotCanvas
                                  values={validValues}
                                  iceLines={validIceLines}
                                  featureName={featureName}
                                  maxIceLines={pdpSection.maxIceLines}
                                />

                                {/* Y-axis labels */}
                                <div className="absolute left-0 top-4 bottom-14 flex flex-col justify-between text-xs text-gray-600" style={{ width: '48px' }}>
                                  {[paddedMaxY, (paddedMaxY * 2 + paddedMinY) / 3, (paddedMaxY + paddedMinY * 2) / 3, paddedMinY].map((val, labelIdx) => (
                                    <div key={labelIdx} className="text-right pr-2">
                                      {val.toFixed(2)}
                                    </div>
                                  ))}
                                </div>

                                {/* X-axis labels */}
                                <div className="absolute bottom-0 left-14 right-4 flex justify-between text-xs text-gray-600" style={{ height: '40px', paddingTop: '4px' }}>
                                  {[0, 0.2, 0.4, 0.6, 0.8, 1].map((ratio, labelIdx) => {
                                    const val = minX + ratio * rangeX;
                                    return (
                                      <span key={labelIdx} className="text-center" style={{ width: '16.66%' }}>
                                        {val >= 1000 ? `${(val / 1000).toFixed(0)}k` : val.toFixed(0)}
                                      </span>
                                    );
                                  })}
                                </div>

                                {/* Y-axis label */}
                                <div
                                  className="absolute text-xs font-medium text-gray-700 whitespace-nowrap origin-center"
                                  style={{
                                    left: '12px',
                                    top: '50%',
                                    transform: 'translateY(-50%) rotate(-90deg)',
                                    transformOrigin: 'center'
                                  }}
                                >
                                  Prediction Probability
                                </div>

                                {/* X-axis label */}
                                <div
                                  className="absolute text-xs font-medium text-gray-700 text-center"
                                  style={{
                                    bottom: '8px',
                                    left: '56px',
                                    right: '16px'
                                  }}
                                >
                                  {displayName}
                                </div>
                              </div>

                              {/* Legend */}
                              <div className="mt-4 flex items-center justify-center gap-6 text-xs">
                                <div className="flex items-center gap-2">
                                  <div className="w-8 h-0.5 bg-gray-300"></div>
                                  <span className="text-gray-600">
                                    ICE Lines {totalIceLines > displayIceLines.length ? `(${displayIceLines.length.toLocaleString()}/${totalIceLines.toLocaleString()} shown)` : `(${totalIceLines.toLocaleString()})`}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <div className="w-8 h-0.5 bg-cyan-500" style={{ height: '3px' }}></div>
                                  <span className="text-gray-600">PDP Line</span>
                                </div>
                              </div>
                            </div>
                          );
                        }).filter(Boolean);
                      })()}
                    </div>
                  ) : (
                    <p className="text-gray-500 text-center py-4">No PDP data available</p>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="pl-6">
            <p className="text-gray-700">You didn't generate AI Explainability! Go to Model Performance page and generate explainability insights.</p>
          </div>
        )}
          </>
        )}
      </CollapsibleSection>

      {/* MODEL OWNER Section */}
      <CollapsibleSection sectionNumber={10} sectionTitle="MODEL OWNER" defaultExpanded={false}>
        {() => (
          <>

        <div className="pl-6 space-y-4">
          {/* Approved By - Editable */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-700">The model will be approved by:</p>
            <EditableField
              value={documentationData.modelOwner.approvedBy || ''}
              onSave={(value) => updateModelOwner({ approvedBy: value })}
            />
          </div>

          {/* Created By - Read-only */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-700">Model created by:</p>
            <p className="text-gray-900">{documentationData.modelOwner.createdBy || 'Unknown User'}</p>
          </div>

          {/* Created On - Read-only */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-700">Created on:</p>
            <p className="text-gray-900">
              {documentationData.modelOwner.createdOn 
                ? new Date(documentationData.modelOwner.createdOn).toLocaleString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })
                : 'Not available'}
            </p>
          </div>
            </div>
          </>
        )}
      </CollapsibleSection>

      {/* Download Button */}
      <div className="border-t border-gray-300 pt-6 flex justify-center">
        <button
          onClick={onDownload}
          disabled={isDownloading}
          className="px-6 py-3 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed transition-colors flex items-center space-x-2 relative"
        >
          {isDownloading ? (
            <>
              <Loader className="h-5 w-5 animate-spin" />
              <span>Downloading...</span>
            </>
          ) : (
            <>
              <Download className="h-5 w-5" />
              <span>Download Documentation</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default DocumentationViewer;

