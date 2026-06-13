import React, { useState, useEffect, Component, ErrorInfo, ReactNode } from 'react';
import { FileText, Loader, AlertTriangle } from 'lucide-react';
import { useDocumentation } from '../../contexts/DocumentationContext';
import { useUser } from '../../contexts/UserContext';
import DocumentationViewer from '../DocumentationViewer';
import { fastApiService } from '../../services/fastApiService';
import { buildModelSelectionSummary, getDefaultModelSelectionSummary } from '../../utils/modelSelectionSummary';
import { modelEvaluationService } from '../../services/modelEvaluationService';
import { bivariateAnalysisService } from '../../services/bivariateAnalysisService';

// Error Boundary Component
interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('❌ ErrorBoundary caught an error:', error);
    console.error('Error details:', errorInfo);
    this.setState({
      error,
      errorInfo,
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="bg-white rounded-lg border border-red-200 p-8">
          <div className="max-w-2xl mx-auto text-center space-y-4">
            <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto">
              <AlertTriangle className="h-10 w-10 text-red-600" />
            </div>
            <div>
              <h3 className="text-2xl font-bold text-gray-900 mb-2">Error Loading Documentation</h3>
              <p className="text-gray-600 mb-4">
                An error occurred while rendering the documentation viewer. This might be due to incomplete data or a rendering issue.
              </p>
              {this.state.error && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-left">
                  <p className="text-sm text-gray-700 font-mono break-all">
                    {this.state.error.toString()}
                  </p>
                </div>
              )}
              <button
                onClick={() => {
                  this.setState({ hasError: false, error: null, errorInfo: null });
                  window.location.reload();
                }}
                className="mt-4 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Reload Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

interface Step9ModelDocumentationProps {
  // Chat component
  renderStepChat: (step: number) => React.ReactNode;
}

const Step9ModelDocumentation: React.FC<Step9ModelDocumentationProps> = ({
  renderStepChat,
}) => {
  const { 
    documentationData, 
    updateModelObjective, 
    updateDataSummary,
    updateDataOverview,
    updateTargetDefinition,
    updateSamplingPlan,
    updateSegmentation,
    updateDataTreatment,
    updateModelValidation,
    updateModelSelection,
    updateModelOwner,
    updateModelPerformance,
    updateDataInsights,
    updateFeatureEngineering,
    generateDocumentation, 
    isDocumentationGenerated 
  } = useDocumentation();
  
  const { user } = useUser();
  
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [showDocumentation, setShowDocumentation] = useState(isDocumentationGenerated);

  // Update showDocumentation when isDocumentationGenerated changes
  useEffect(() => {
    setShowDocumentation(isDocumentationGenerated);
  }, [isDocumentationGenerated]);

  const handleGenerateDocumentation = async () => {
    console.log('🎬 ========================================');
    console.log('🎬 DOCUMENTATION GENERATION STARTED');
    console.log('🎬 ========================================');
    
    setIsGenerating(true);
    
    // Store best model info for use in explainability extraction
    let bestModelInfo: { modelName: string; modelId: string } | null = null;
    
    try {
      // 1. Get Model Objective data from session storage
      const datasetConfig = sessionStorage.getItem('dataset_config');
      const selectedProject = sessionStorage.getItem('selected_project');
      
      console.log('📋 Documentation Generation Debug:');
      console.log('  - Dataset Config:', datasetConfig);
      console.log('  - Selected Project:', selectedProject);
      
      let modelObjective = {
        description: '',
        problemStatement: ''
      };

      // Get project description from selected project
      if (selectedProject) {
        try {
          const project = JSON.parse(selectedProject);
          console.log('  - Parsed Project:', project);
          console.log('  - Project Description:', project.description);
          modelObjective.description = project.description || '';
        } catch (e) {
          console.error('  ❌ Failed to parse selected project:', e);
        }
      } else {
        console.warn('  ⚠️ No selected project found in sessionStorage');
      }

      // Get problem statement from dataset config
      if (datasetConfig) {
        try {
          const config = JSON.parse(datasetConfig);
          console.log('  - Parsed Config:', config);
          console.log('  - Problem Statement:', config.problem_statement);
          modelObjective.problemStatement = config.problem_statement || '';
        } catch (e) {
          console.error('  ❌ Failed to parse dataset config:', e);
        }
      } else {
        console.warn('  ⚠️ No dataset config found in sessionStorage');
      }
      
      console.log('  - Final Model Objective:', modelObjective);
      updateModelObjective(modelObjective);

      // 2. Generate Data Summary if not already generated or if data has changed
      const shouldGenerateDataSummary = !documentationData.objectives.dataSummary.content || 
        documentationData.objectives.dataSummary.metadata.lastGenerated === null;

      if (shouldGenerateDataSummary) {
        // Prepare data for LLM generation
        const datasetAnalysisStr = sessionStorage.getItem('dataset_analysis');
        const dataDictionary = datasetConfig ? JSON.parse(datasetConfig).data_dictionary || null : null;
        
        let columns: string[] = [];
        if (datasetAnalysisStr) {
          const analysis = JSON.parse(datasetAnalysisStr);
          columns = analysis.columns?.map((col: any) => col.name) || [];
        }

        // Call backend to generate data summary
        const summaryResponse = await fastApiService.generateDataSummary({
          columns,
          data_dictionary: dataDictionary,
          model_objective: modelObjective.problemStatement || modelObjective.description,
        });

        if (summaryResponse.success && summaryResponse.summary) {
          updateDataSummary({
            content: summaryResponse.summary,
            metadata: {
              columns,
              dataDictionary,
              lastGenerated: new Date().toISOString(),
            }
          });
        } else {
          console.error('Failed to generate data summary:', summaryResponse.error);
          // Set a default message if generation fails
          updateDataSummary({
            content: 'Data summary generation failed. Please try again or edit manually.',
            metadata: {
              columns,
              dataDictionary,
              lastGenerated: new Date().toISOString(),
            }
          });
        }
      }

      // 3. Collect Model Design Data
      const datasetAnalysisStr = sessionStorage.getItem('dataset_analysis');
      let knowledgeGraphStr = sessionStorage.getItem('knowledge_graph_result');
      
      console.log('📊 Model Design Data Collection:');
      console.log('  - Dataset Analysis String:', datasetAnalysisStr ? 'Found' : 'NOT FOUND');
      console.log('  - Knowledge Graph String:', knowledgeGraphStr ? 'Found' : 'NOT FOUND');
      
      // If knowledge graph not in session, try to fetch from backend
      const datasetId = sessionStorage.getItem('dataset_id');
      if (!knowledgeGraphStr && datasetId) {
        console.log('  - Attempting to fetch knowledge graph from backend...');
        try {
          const kgProgress = await fastApiService.pollKnowledgeGraphProgress(datasetId);
          if (kgProgress?.available && kgProgress.result) {
            knowledgeGraphStr = JSON.stringify(kgProgress.result);
            sessionStorage.setItem('knowledge_graph_result', knowledgeGraphStr);
            console.log('  ✅ Knowledge graph fetched from backend');
          } else {
            console.log('  ⚠️ Knowledge graph not available in backend');
          }
        } catch (error) {
          console.log('  ⚠️ Could not fetch knowledge graph:', error);
        }
      }
      
      if (datasetAnalysisStr) {
        const analysis = JSON.parse(datasetAnalysisStr);
        console.log('  - Parsed Analysis:', analysis);
        
        // 3.1 Dataset Stats
        const numericalCount = analysis.columns?.filter((col: any) => 
          (col.logical_type === 'Numerical' || col.type === 'Numerical')
        ).length || 0;
        
        const categoricalCount = analysis.columns?.filter((col: any) => 
          ((col.logical_type === 'Categorical' || col.type === 'Categorical') && 
           !(col.logical_type === 'Date' || col.is_date))
        ).length || 0;
        
        const dateCount = analysis.columns?.filter((col: any) => 
          (col.logical_type === 'Date' || col.is_date)
        ).length || 0;
        
        const datasetStats = {
          totalRows: analysis.totalRows || 0,
          totalColumns: analysis.totalColumns || 0,
          numericalColumns: numericalCount,
          categoricalColumns: categoricalCount,
          dateColumns: dateCount,
        };
        
        console.log('  - Dataset Stats:', datasetStats);
        
        // 3.2 Variable Categorization (from Knowledge Graph)
        let variableCategorization: any = {
          categories: {},
          colors: {},
          imageData: null,
        };
        
        if (knowledgeGraphStr) {
          try {
            const kgResult = JSON.parse(knowledgeGraphStr);
            if (kgResult.categories && kgResult.nodes) {
              const categoryColors: Record<string, string> = {};
              const categoryCounts: Record<string, number> = {};
              
              // Build color map and initialize counts
              kgResult.categories.forEach((cat: any) => {
                categoryColors[cat.name] = cat.color;
                categoryCounts[cat.name] = 0;
              });
              
              // Count variables per category
              kgResult.nodes.forEach((node: any) => {
                if (node.group && node.group !== 'category') {
                  if (categoryCounts[node.group] !== undefined) {
                    categoryCounts[node.group]++;
                  } else {
                    categoryCounts[node.group] = 1;
                  }
                }
              });
              
              variableCategorization = {
                categories: categoryCounts,
                colors: categoryColors,
                imageData: null, // Will be generated on frontend for now
              };
              
              console.log('  - Variable Categorization:', variableCategorization);
            }
          } catch (e) {
            console.error('  ❌ Failed to parse knowledge graph result:', e);
          }
        } else {
          console.warn('  ⚠️ No knowledge graph data found in sessionStorage');
        }
        
        // 3.3 Quality Metrics
        const emptyColumns = analysis.columns?.filter((col: any) => 
          col.missing_count === analysis.totalRows
        ) || [];
        
        const constantColumns = analysis.columns?.filter((col: any) => 
          col.unique_count === 1
        ) || [];
        
        const sparseColumns = analysis.columns?.filter((col: any) => {
          const missingPercentage = (col.missing_count / analysis.totalRows) * 100;
          return missingPercentage > 50 && missingPercentage < 100;
        }) || [];
        
        // Detect formatting issues
        const formattingIssueColumns = analysis.columns?.filter((col: any) => {
          if (col.type === 'Categorical' && col.sample_values) {
            const values = Object.keys(col.sample_values);
            const lowerCaseValues = values.map((v: string) => v.toLowerCase());
            const uniqueLowerCase = new Set(lowerCaseValues);
            if (uniqueLowerCase.size < values.length) return true;
            
            const hasWhitespaceIssues = values.some((v: string) => v !== v.trim());
            if (hasWhitespaceIssues) return true;
          }
          return false;
        }) || [];
        
        const qualityMetrics = {
          emptyColumns: emptyColumns.length,
          constantColumns: constantColumns.length,
          sparseColumns: sparseColumns.length,
          formattingIssues: formattingIssueColumns.length,
          emptyColumnNames: emptyColumns.map((col: any) => col.name),
          constantColumnNames: constantColumns.map((col: any) => col.name),
          sparseColumnNames: sparseColumns.map((col: any) => col.name),
          formattingIssueColumnNames: formattingIssueColumns.map((col: any) => col.name),
        };
        
        console.log('  - Quality Metrics:', qualityMetrics);
        
        // Build recommendations
        const recommendations: string[] = [];
        if (emptyColumns.length > 0) {
          recommendations.push(`${emptyColumns.length} columns have 100% missing rate. Consider dropping them.`);
        }
        if (constantColumns.length > 0) {
          recommendations.push(`${constantColumns.length} constant columns found. Consider removing them.`);
        }
        if (formattingIssueColumns.length > 0) {
          recommendations.push(`${formattingIssueColumns.length} formatting issues detected. Review data consistency.`);
        }
        if (recommendations.length === 0) {
          recommendations.push('Data quality appears good for modeling.');
        }
        
        // 3.4 Generate Data Quality Summary (if needed)
        const shouldGenerateQualitySummary = !documentationData.modelDesign.dataOverview.dataQuality.summary ||
          documentationData.modelDesign.dataOverview.dataQuality.lastGenerated === null;
        
        let dataQualitySummary = documentationData.modelDesign.dataOverview.dataQuality.summary;
        
        if (shouldGenerateQualitySummary) {
          const qualitySummaryResponse = await fastApiService.generateDataQualitySummary({
            metrics: qualityMetrics,
            recommendations,
            totalRows: analysis.totalRows,
            totalColumns: analysis.totalColumns,
          });
          
          if (qualitySummaryResponse.success && qualitySummaryResponse.summary) {
            dataQualitySummary = qualitySummaryResponse.summary;
          } else {
            console.error('Failed to generate data quality summary:', qualitySummaryResponse.error);
            dataQualitySummary = 'Data quality summary generation failed. Please try again or edit manually.';
          }
        }
        
        // 3.4.1 Fetch Column Details (EDA Report) for Data Overview
        console.log('📊 Fetching Column Details (EDA Report) for Data Overview:');
        let edaReportTable: Array<{
          Column: string;
          'Data Types': string;
          Unique: number;
          Missing: number;
          Mean?: number | string;
          Median?: number | string;
          Mode?: string;
          Std?: number | string;
          Var?: number | string;
          Min?: number | string;
          'p5%'?: number | string;
          'p25%'?: number | string;
          'p50%'?: number | string;
          'p75%'?: number | string;
          'p95%'?: number | string;
          'p99%'?: number | string;
          Max?: number | string;
        }> = [];
        
        if (datasetId) {
          try {
            const columnInfoResponse = await fastApiService.getColumnInfo(datasetId);
            if (columnInfoResponse.success && columnInfoResponse.columns_info) {
              console.log(`  ✅ Fetched column info for ${columnInfoResponse.columns_info.length} columns`);
              
              edaReportTable = columnInfoResponse.columns_info.map((col: any) => {
                // Determine column type
                const columnType: 'Numerical' | 'Categorical' | 'Date' = col.column_type || 
                  (col.data_type && (col.data_type.toLowerCase().includes('date') || col.data_type.toLowerCase().includes('time')) ? 'Date' :
                  ['int64', 'float64', 'int32', 'float32'].includes(col.data_type) ? 'Numerical' : 'Categorical') as 'Numerical' | 'Categorical' | 'Date';
                const isNumeric = columnType === 'Numerical';
                const isDate = columnType === 'Date';
                
                return {
                  Column: col.column_name || '',
                  'Data Types': columnType,
                  Unique: col.unique_count || 0,
                  Missing: col.missing_count || 0,
                  Mean: isNumeric && !isDate ? (col.mean !== null && col.mean !== undefined ? Number(col.mean) : '') : '',
                  Median: isNumeric && !isDate ? (col.median !== null && col.median !== undefined ? Number(col.median) : '') : '',
                  Mode: !isDate && col.mode !== null && col.mode !== undefined ? String(col.mode) : '',
                  Std: isNumeric && !isDate ? (col.standard_deviation !== null && col.standard_deviation !== undefined ? Number(col.standard_deviation) : '') : '',
                  Var: isNumeric && !isDate ? (col.variance !== null && col.variance !== undefined ? Number(col.variance) : '') : '',
                  Min: isNumeric && !isDate ? (col.min_value !== null && col.min_value !== undefined ? Number(col.min_value) : '') : '',
                  'p5%': isNumeric && !isDate ? (col.percentile_5 !== null && col.percentile_5 !== undefined ? Number(col.percentile_5) : '') : '',
                  'p25%': isNumeric && !isDate ? (col.percentile_25 !== null && col.percentile_25 !== undefined ? Number(col.percentile_25) : '') : '',
                  'p50%': isNumeric && !isDate ? (col.percentile_50 !== null && col.percentile_50 !== undefined ? Number(col.percentile_50) : '') : '',
                  'p75%': isNumeric && !isDate ? (col.percentile_75 !== null && col.percentile_75 !== undefined ? Number(col.percentile_75) : '') : '',
                  'p95%': isNumeric && !isDate ? (col.percentile_95 !== null && col.percentile_95 !== undefined ? Number(col.percentile_95) : '') : '',
                  'p99%': isNumeric && !isDate ? (col.percentile_99 !== null && col.percentile_99 !== undefined ? Number(col.percentile_99) : '') : '',
                  Max: isNumeric && !isDate ? (col.max_value !== null && col.max_value !== undefined ? Number(col.max_value) : '') : '',
                };
              });
              
              console.log(`  ✅ Built EDA Report table with ${edaReportTable.length} rows`);
            } else {
              console.warn('  ⚠️ Column info not available');
            }
          } catch (error) {
            console.error('  ❌ Failed to fetch column info:', error);
          }
        } else {
          console.warn('  ⚠️ No dataset ID available, skipping column info fetch');
        }

        // Update Data Overview in context
        console.log('  ✅ Updating Data Overview in context');
        updateDataOverview({
          datasetStats,
          variableCategorization,
          dataQuality: {
            summary: dataQualitySummary,
            metrics: qualityMetrics,
            recommendations,
            lastGenerated: shouldGenerateQualitySummary ? new Date().toISOString() : documentationData.modelDesign.dataOverview.dataQuality.lastGenerated,
          },
          edaReport: {
            table: edaReportTable,
            rowsToShow: 20,
          },
        });

        // 3.5 Collect Target Definition Data
        console.log('🎯 Collecting Target Definition Data:');
        
        const targetVariable = datasetConfig ? JSON.parse(datasetConfig).target_variable : null;
        console.log('  - Target Variable:', targetVariable);
        
        if (targetVariable) {
          // Get target definition
          const shouldGenerateDefinition = !documentationData.modelDesign.targetDefinition.definition ||
            documentationData.modelDesign.targetDefinition.lastGenerated === null;
          
          let targetDefinition = documentationData.modelDesign.targetDefinition.definition;
          
          if (shouldGenerateDefinition) {
            const dataDictionary = datasetConfig ? JSON.parse(datasetConfig).data_dictionary || null : null;
            const problemStatement = datasetConfig ? JSON.parse(datasetConfig).problem_statement || null : null;
            const columns = analysis.columns?.map((col: any) => col.name) || [];
            
            console.log('  - Generating target definition...');
            const definitionResponse = await fastApiService.generateTargetDefinition({
              target_variable: targetVariable,
              data_dictionary: dataDictionary,
              columns: columns,
              problem_statement: problemStatement,
            });
            
            if (definitionResponse.success && definitionResponse.definition) {
              targetDefinition = definitionResponse.definition;
              console.log('  ✅ Target definition:', targetDefinition);
            } else {
              console.error('  ❌ Failed to generate target definition:', definitionResponse.error);
              targetDefinition = 'Target definition not available.';
            }
          }
          
          // Calculate event rate
          const datasetId = sessionStorage.getItem('dataset_id');
          let eventRate = { eventCount: 0, totalCount: 0, percentage: 0 };
          
          if (datasetId) {
            console.log('  - Calculating event rate...');
            const eventRateResponse = await fastApiService.calculateEventRate({
              dataset_id: datasetId,
              target_variable: targetVariable,
            });
            
            if (eventRateResponse.success) {
              eventRate = {
                eventCount: eventRateResponse.event_count || 0,
                totalCount: eventRateResponse.total_count || 0,
                percentage: eventRateResponse.percentage || 0,
              };
              console.log('  ✅ Event rate:', eventRate);
            } else {
              console.error('  ❌ Failed to calculate event rate:', eventRateResponse.error);
            }
          }
          
          // Update Target Definition in context
          updateTargetDefinition({
            targetVariableName: targetVariable,
            definition: targetDefinition,
            eventRate: eventRate,
            lastGenerated: shouldGenerateDefinition ? new Date().toISOString() : documentationData.modelDesign.targetDefinition.lastGenerated,
          });

          // 2.5 Generate Model Objective (after Data Summary and Target Definition are ready)
          console.log('🎯 Generating Model Objective:');
          const shouldGenerateModelObjective = !documentationData.objectives.modelObjective.generatedObjective ||
            documentationData.objectives.modelObjective.lastGenerated === null;
          
          if (shouldGenerateModelObjective) {
            const dataSummaryContent = documentationData.objectives.dataSummary.content || '';
            
            console.log('  - Generating model objective...');
            const objectiveResponse = await fastApiService.generateModelObjective({
              project_description: modelObjective.description || null,
              problem_statement: modelObjective.problemStatement || null,
              data_summary: dataSummaryContent || null,
              target_variable_name: targetVariable || null,
              target_definition: targetDefinition || null,
            });
            
            if (objectiveResponse.success && objectiveResponse.objective) {
              console.log('  ✅ Model objective generated:', objectiveResponse.objective);
              updateModelObjective({
                generatedObjective: objectiveResponse.objective,
                lastGenerated: new Date().toISOString(),
              });
            } else {
              console.error('  ❌ Failed to generate model objective:', objectiveResponse.error);
              // Set a default message if generation fails
              updateModelObjective({
                generatedObjective: 'Model objective generation failed. Please try again or edit manually.',
                lastGenerated: new Date().toISOString(),
              });
            }
          } else {
            console.log('  - Using existing model objective');
          }

          // 3.6 Collect Sampling Plan Data
          console.log('📊 Collecting Sampling Plan Data:');
          
          if (datasetId) {
            const samplingPlanResponse = await fastApiService.getSamplingPlan({
              dataset_id: datasetId,
              target_variable: targetVariable,
            });
            
            if (samplingPlanResponse.success) {
              console.log('  ✅ Sampling plan retrieved');
              console.log('    - Has Split:', samplingPlanResponse.has_split);
              console.log('    - Train:', samplingPlanResponse.train);
              console.log('    - Hold:', samplingPlanResponse.hold);
              
              // Get sampling identifier from config
              const config = datasetConfig ? JSON.parse(datasetConfig) : {};
              const samplingIdentifier = config.sample_identifier_variable || '';
              console.log('  - Sampling Identifier from config:', samplingIdentifier);
              
              // Map API response (snake_case) to context (camelCase)
              const trainData = samplingPlanResponse.train ? {
                total: samplingPlanResponse.train.total,
                eventCount: samplingPlanResponse.train.event_count,
                eventRate: samplingPlanResponse.train.event_rate,
              } : { total: 0, eventCount: 0, eventRate: 0 };
              
              const holdData = samplingPlanResponse.hold ? {
                total: samplingPlanResponse.hold.total,
                eventCount: samplingPlanResponse.hold.event_count,
                eventRate: samplingPlanResponse.hold.event_rate,
              } : { total: 0, eventCount: 0, eventRate: 0 };
              
              const samplingPlanData = {
                hasSplit: samplingPlanResponse.has_split || false,
                train: trainData,
                hold: holdData,
                samplingIdentifier: samplingIdentifier,
              };
              
              updateSamplingPlan(samplingPlanData);
              
              // Generate LLM writeup for sampling plan
              console.log('  📝 Generating sampling plan writeup...');
              try {
                const writeupResponse = await fastApiService.generateSamplingPlanWriteup({
                  sampling_plan: {
                    hasSplit: samplingPlanData.hasSplit,
                    train: samplingPlanData.train,
                    hold: samplingPlanData.hold,
                  },
                });
                
                if (writeupResponse.success && writeupResponse.writeup) {
                  console.log('  ✅ Sampling plan writeup generated');
                  updateSamplingPlan({
                    ...samplingPlanData,
                    writeup: writeupResponse.writeup,
                  });
                } else {
                  console.warn('  ⚠️ Failed to generate sampling plan writeup:', writeupResponse.error);
                }
              } catch (error) {
                console.error('  ❌ Error generating sampling plan writeup:', error);
              }
            } else {
              console.error('  ❌ Failed to get sampling plan:', samplingPlanResponse.error);
            }
          }

          // 3.7 Collect Segmentation Data
          console.log('📊 Collecting Segmentation Data:');
          
          const segmentationResult = sessionStorage.getItem('segmentation_result');
          
          if (segmentationResult) {
            try {
              const segResult = JSON.parse(segmentationResult);
              console.log('  - Segmentation Result:', segResult);
              
              if (segResult.success && segResult.segments && segResult.segments.length > 0) {
                const segments = segResult.segments.map((seg: any, index: number) => ({
                  segmentNumber: index + 1,
                  rule: seg.rules_readable || seg.rules?.join(', ') || 'No rule specified',
                  total: seg.size || 0,
                  eventRate: (seg.event_rate * 100) || 0, // Convert to percentage
                  segmentDistribution: (seg.proportion * 100) || 0, // Convert to percentage
                }));
                
                console.log('  ✅ Segmentation data collected:', segments);
                
                // Prepare chart data for Segment Sizes and Segment Proportions
                const segmentLabels = segments.map((s: any) => `Segment ${s.segmentNumber}`);
                const segmentSizesData = segments.map((s: any) => s.total);
                const segmentProportionsData = segments.map((s: any) => s.segmentDistribution);
                
                // Get event rates from viability data or from segments
                // Event rates should be in decimal format (0-1) for the chart
                const eventRates = segResult.viability?.segment_event_rates || 
                  segments.map((s: any) => {
                    // If eventRate is already a percentage (e.g., 9.31), convert to decimal (0.0931)
                    // If it's already a decimal (e.g., 0.0931), use as is
                    const rate = s.eventRate;
                    return rate > 1 ? rate / 100 : rate;
                  });
                
                // Compute IV report from segments (similar to DatasetOverviewSidebar)
                const computeIVReport = (segments: any[]) => {
                  if (!segments || segments.length === 0) return null;
                  
                  const table = segments.map((s: any, idx: number) => {
                    const Ni = Number(s.total || 0);
                    const badRate = typeof s.eventRate === 'number' ? (s.eventRate / 100) : 0; // Convert percentage to decimal
                    const Bi = Math.round(Ni * badRate);
                    const Gi = Math.max(Ni - Bi, 0);
                    return {
                      segment_id: idx,
                      accounts: Ni,
                      bads: Bi,
                      goods: Gi,
                      bad_rate: Ni > 0 ? Bi / Ni : 0
                    };
                  });
                  
                  const N = table.reduce((acc, r) => acc + r.accounts, 0);
                  const GT = table.reduce((acc, r) => acc + r.goods, 0);
                  const BT = table.reduce((acc, r) => acc + r.bads, 0);
                  
                  const epsG = GT === 0 ? 1e-12 : 0;
                  const epsB = BT === 0 ? 1e-12 : 0;
                  
                  const enriched = table.map(r => {
                    const dist_goods = GT > 0 ? r.goods / (GT + epsG) : 0;
                    const dist_bads = BT > 0 ? r.bads / (BT + epsB) : 0;
                    const g = dist_goods > 0 ? dist_goods : 1e-12;
                    const b = dist_bads > 0 ? dist_bads : 1e-12;
                    const woe = Math.log(g / b);
                    const iv_contribution = (dist_goods - dist_bads) * woe;
                    return { ...r, dist_goods, dist_bads, woe, iv_contribution };
                  });
                  
                  const totalIV = Math.max(enriched.reduce((acc, r) => acc + r.iv_contribution, 0), 0);
                  const IV_BENCHMARKS: Array<[number, number, string]> = [
                    [0.0, 0.02, 'Useless'],
                    [0.02, 0.10, 'Weak'],
                    [0.10, 0.30, 'Medium'],
                    [0.30, 0.50, 'Strong'],
                    [0.50, Number.POSITIVE_INFINITY, 'Very Strong / Suspicious']
                  ];
                  const bucket = IV_BENCHMARKS.find(([lo, hi]) => totalIV >= lo && totalIV < hi)?.[2] || 'Useless';
                  
                  return {
                    table: enriched,
                    totals: { N, GT, BT, bad_rate: N > 0 ? BT / N : 0, IV: totalIV },
                    interpretation: { bucket }
                  };
                };
                
                const ivReport = computeIVReport(segments);
                
                // Generate segmentation understanding using LLM
                console.log('  📝 Generating segmentation understanding...');
                let understandingContent = '';
                try {
                  const dataSummary = documentationData.objectives.dataSummary.content || '';
                  const understandingResponse = await fastApiService.generateSegmentationUnderstanding({
                    data_summary: dataSummary,
                    segments: segments.map((s: any) => ({
                      rule: s.rule,
                      total: s.total,
                      eventRate: s.eventRate,
                      segmentDistribution: s.segmentDistribution,
                    })),
                    segment_sizes: segmentSizesData,
                    segment_proportions: segmentProportionsData,
                    event_rates: segments.map((s: any) => s.eventRate), // Already in percentage format
                    iv_report: ivReport ? {
                      table: ivReport.table.map((r: any) => ({
                        segment_id: r.segment_id,
                        woe: r.woe,
                        iv_contribution: r.iv_contribution,
                        bad_rate: r.bad_rate,
                      })),
                    } : undefined,
                  });
                  
                  if (understandingResponse.success && understandingResponse.understanding) {
                    understandingContent = understandingResponse.understanding;
                    console.log('  ✅ Segmentation understanding generated');
                  } else {
                    console.warn('  ⚠️ Failed to generate segmentation understanding:', understandingResponse.error);
                  }
                } catch (e) {
                  console.error('  ❌ Error generating segmentation understanding:', e);
                }
                
                updateSegmentation({
                  hasSegmentation: true,
                  variablesUsed: segResult.variables_used || [],
                  method: segResult.method || '',
                  segments: segments,
                  segmentSizesChart: {
                    labels: segmentLabels,
                    data: segmentSizesData,
                    eventRates: eventRates,
                  },
                  segmentProportionsChart: {
                    labels: segmentLabels,
                    data: segmentProportionsData,
                    colors: [
                      '#3b82f6',
                      '#10b981',
                      '#f59e0b',
                      '#8b5cf6',
                      '#ef4444',
                      '#06b6d4',
                      '#ec4899',
                    ].slice(0, segments.length),
                  },
                  ivVisualizationCharts: ivReport ? {
                    ivReport: ivReport,
                    ivStrength: {
                      value: ivReport.totals.IV,
                      label: ivReport.interpretation.bucket,
                    },
                  } : undefined,
                  understanding: understandingContent ? {
                    content: understandingContent,
                    lastGenerated: new Date().toISOString(),
                  } : undefined,
                });
              } else {
                console.log('  ℹ️ No segments found');
                updateSegmentation({
                  hasSegmentation: false,
                  segments: [],
                });
              }
            } catch (e) {
              console.error('  ❌ Failed to parse segmentation result:', e);
              updateSegmentation({
                hasSegmentation: false,
                segments: [],
              });
            }
          } else {
            console.log('  ℹ️ No segmentation performed');
            updateSegmentation({
              hasSegmentation: false,
              segments: [],
            });
          }

        // 3.7 Collect Data Treatment Data
          console.log('📊 Collecting Data Treatment Data:');
          
          try {
            if (!datasetId) {
              console.warn('  ⚠️ No dataset ID available, skipping data treatment');
              return;
            }
            
            // Get quality check plan
            const qualityCheckPlanResult = await fastApiService.getQualityCheckPlan(datasetId);
            console.log('  - Quality check plan result:', qualityCheckPlanResult.success ? 'Success' : 'Failed');
            
            // Get column stats
            const columnStatsResult = await fastApiService.getColumnStats(datasetId);
            console.log('  - Column stats result:', columnStatsResult.success ? 'Success' : 'Failed');
            
            if (qualityCheckPlanResult.success && columnStatsResult.success) {
              // Generate write-up using both tables
              const writeupResult = await fastApiService.generateQualityChangesWriteup({
                quality_check_plan: qualityCheckPlanResult.plan || { table: [] },
                column_stats: columnStatsResult.stats || [],
              });
              
              console.log('  - Quality changes write-up result:', writeupResult.success ? 'Success' : 'Failed');
              
              updateDataTreatment({
                qualityCheckPlan: {
                  table: qualityCheckPlanResult.plan?.table || [],
                  rowsToShow: 20,
                },
                implementedQualityChanges: {
                  columnStats: columnStatsResult.stats || [],
                  rowsToShow: 20,
                  writeup: writeupResult.success && writeupResult.writeup ? {
                    content: writeupResult.writeup,
                    lastGenerated: new Date().toISOString(),
                  } : undefined,
                },
              });
            } else {
              console.warn('  ⚠️ Failed to fetch data treatment data');
              updateDataTreatment({
                qualityCheckPlan: {
                  table: [],
                  rowsToShow: 20,
                },
                implementedQualityChanges: {
                  columnStats: [],
                  rowsToShow: 20,
                },
              });
            }
          } catch (e) {
            console.error('  ❌ Failed to fetch data treatment data:', e);
            updateDataTreatment({
              qualityCheckPlan: {
                table: [],
                rowsToShow: 20,
              },
              implementedQualityChanges: {
                columnStats: [],
                rowsToShow: 20,
              },
            });
          }

        // 3.9 Collect Data Insights
          console.log('📊 Collecting Data Insights:');
          try {
            if (!datasetId) {
              console.warn('  ⚠️ No dataset ID available, skipping data insights');
              return;
            }
            const dataInsightsResult = await fastApiService.getDataInsights(datasetId);
            console.log('  - Data insights result:', dataInsightsResult.success ? 'Success' : 'Failed');
            console.log('  - Data insights keys:', dataInsightsResult.insights ? Object.keys(dataInsightsResult.insights) : 'No insights');
            
            if (dataInsightsResult.success && dataInsightsResult.insights) {
              const insights = dataInsightsResult.insights;
              console.log('  - Available insight types:', Object.keys(insights));
              
              // Process bivariate analysis if available
              if (insights.bivariate_analysis) {
                updateDataInsights({
                  bivariateAnalysis: {
                    insights: insights.bivariate_analysis.insights || [],
                    edaReport: insights.bivariate_analysis.eda_report || [],
                    rowsToShow: insights.bivariate_analysis.rows_to_show || 'used_features',
                  },
                });
                console.log('  - Bivariate analysis data loaded:', {
                  insights: (insights.bivariate_analysis.insights || []).length,
                  edaReport: (insights.bivariate_analysis.eda_report || []).length,
                });
              } else {
                console.warn('  ⚠️ No bivariate analysis data found');
              }
              
              // Process IV analysis if available
              if (insights.iv_analysis) {
                updateDataInsights({
                  ivAnalysis: {
                    insights: insights.iv_analysis.insights || [],
                    edaReport: insights.iv_analysis.eda_report || [],
                    rowsToShow: insights.iv_analysis.rows_to_show || 'used_features',
                  },
                });
                console.log('  - IV analysis data loaded:', {
                  insights: (insights.iv_analysis.insights || []).length,
                  edaReport: (insights.iv_analysis.eda_report || []).length,
                });
              } else {
                console.warn('  ⚠️ No IV analysis data found');
              }
              
              // Process Correlation Matrix analysis if available
              if (insights.correlation_analysis) {
                updateDataInsights({
                  correlationAnalysis: {
                    insights: insights.correlation_analysis.insights || [],
                    edaReport: insights.correlation_analysis.eda_report || [],
                    rowsToShow: insights.correlation_analysis.rows_to_show || 'used_features',
                  },
                });
                console.log('  - Correlation Matrix analysis data loaded:', {
                  insights: (insights.correlation_analysis.insights || []).length,
                  edaReport: (insights.correlation_analysis.eda_report || []).length,
                });
              } else {
                console.warn('  ⚠️ No Correlation Matrix analysis data found');
              }

              // Process Correlation Analysis (Numeric) if available - NEW
              if (insights.correlation_analysis_numeric) {
                updateDataInsights({
                  correlationAnalysisNumeric: {
                    insights: insights.correlation_analysis_numeric.insights || [],
                    edaReport: insights.correlation_analysis_numeric.eda_report || [],
                    rowsToShow: insights.correlation_analysis_numeric.rows_to_show || 'used_features',
                  },
                });
                console.log('  - Correlation Analysis (Numeric) data loaded:', {
                  insights: (insights.correlation_analysis_numeric.insights || []).length,
                  edaReport: (insights.correlation_analysis_numeric.eda_report || []).length,
                });
              } else {
                console.warn('  ⚠️ No Correlation Analysis (Numeric) data found');
              }
              
              // Process VIF Analysis if available - NEW
              if (insights.vif_analysis) {
                updateDataInsights({
                  vifAnalysis: {
                    insights: insights.vif_analysis.insights || [],
                    edaReport: insights.vif_analysis.eda_report || [],
                    rowsToShow: insights.vif_analysis.rows_to_show || 'used_features',
                  },
                });
                console.log('  - VIF Analysis data loaded:', {
                  insights: (insights.vif_analysis.insights || []).length,
                  edaReport: (insights.vif_analysis.eda_report || []).length,
                });
              } else {
                console.warn('  ⚠️ No VIF Analysis data found');
              }
            } else {
              console.warn('  ⚠️ Failed to fetch data insights:', dataInsightsResult.error);
              updateDataInsights({});
            }
          } catch (e) {
            console.error('  ❌ Failed to fetch data insights:', e);
            updateDataInsights({});
          }

        // 3.7.1 Collect Feature Engineering Data
          console.log('📊 Collecting Feature Engineering Data:');
          try {
            if (!datasetId) {
              console.warn('  ⚠️ No dataset ID available, skipping feature engineering');
              return;
            }
            const transformedVarsResult = await fastApiService.getTransformedVariables(datasetId);
            console.log('  - Transformed variables result:', transformedVarsResult.success ? 'Success' : 'Failed');
            
            if (transformedVarsResult.success && transformedVarsResult.transformed_variables) {
              // Generate write-up using transformed variables
              const writeupResult = await fastApiService.generateFeatureEngineeringWriteup({
                transformed_variables: transformedVarsResult.transformed_variables,
              });
              
              console.log('  - Feature engineering write-up result:', writeupResult.success ? 'Success' : 'Failed');
              
              updateFeatureEngineering({
                transformedVariables: transformedVarsResult.transformed_variables,
                rowsToShow: 20,
                writeup: writeupResult.success && writeupResult.writeup ? {
                  content: writeupResult.writeup,
                  lastGenerated: new Date().toISOString(),
                } : undefined,
              });
              console.log('  - Transformed variables data loaded:', transformedVarsResult.transformed_variables.length, 'variables');
            } else {
              console.warn('  ⚠️ No transformed variables data found');
              updateFeatureEngineering({
                transformedVariables: [],
                rowsToShow: 20,
              });
            }
          } catch (e) {
            console.error('  ❌ Failed to fetch transformed variables:', e);
            updateFeatureEngineering({
              transformedVariables: [],
              rowsToShow: 20,
            });
          }

        // 3.8 Collect Model Validation Data
          console.log('📊 Collecting Model Validation Data:');
          console.log('  - Strategy: Use stored comparison models from Model Evaluation page');
          
          try {
            const modelComparisonDataStr = sessionStorage.getItem('model_comparison_data');
            console.log('  - model_comparison_data in sessionStorage:', modelComparisonDataStr ? 'Found' : 'Not Found');
            
            if (!modelComparisonDataStr) {
              console.warn('  ⚠️ No model comparison data found. User may not have visited Model Evaluation page.');
              updateModelValidation({
                hasHoldDataset: false,
                bestModel: {
                  modelName: '',
                  metrics: {
                    accuracy: 0,
                    precision: 0,
                    recall: 0,
                    f1Score: 0,
                    aucRoc: 0,
                    aucPr: 0,
                    logLoss: 0,
                  },
                },
              });
            } else {
              const comparisonModels = JSON.parse(modelComparisonDataStr);
              console.log('  - Found', comparisonModels.length, 'comparison models');
              
              if (comparisonModels.length === 0) {
                console.warn('  ⚠️ No models in comparison data');
                updateModelValidation({
                  hasHoldDataset: false,
                  bestModel: {
                    modelName: '',
                    metrics: {
                      accuracy: 0,
                      precision: 0,
                      recall: 0,
                      f1Score: 0,
                      aucRoc: 0,
                      aucPr: 0,
                      logLoss: 0,
                    },
                  },
                });
              } else {
                // Log all models for debugging
                console.log('  📊 All Models with Metrics:');
                comparisonModels.forEach((model: any, index: number) => {
                  console.log(`    Model ${index + 1}: ${model.modelName}`);
                  console.log(`      - Model ID: ${model.modelId}`);
                  console.log(`      - Has testAccuracy:`, model.testAccuracy !== undefined && model.testAccuracy !== null);
                  console.log(`      - testAccuracy:`, model.testAccuracy);
                  console.log(`      - testAucRoc:`, model.testAucRoc);
                  console.log(`      - aucRoc:`, model.aucRoc);
                });
                
                // Get best_model_id from training results (aligned with model training agent's selection)
                let bestModelId: string | null = null;
                const trainingResultsStr = sessionStorage.getItem('training_results');
                if (trainingResultsStr) {
                  try {
                    const trainingResults = JSON.parse(trainingResultsStr);
                    bestModelId = trainingResults?.best_model_selection?.best_model_id || 
                                 trainingResults?.training_results?.best_model_selection?.best_model_id ||
                                 null;
                    console.log('  🔍 Best Model ID from training results:', bestModelId);
                  } catch (e) {
                    console.warn('  ⚠️ Failed to parse training results:', e);
                  }
                }
                
                // Find best model: use best_model_id if available, otherwise fallback to AUC-ROC
                let bestModel = comparisonModels[0];
                let selectionMethod = 'fallback';
                
                if (bestModelId) {
                  // Use the model selected by training agent (based on composite score)
                  const foundModel = comparisonModels.find((m: any) => m.modelId === bestModelId);
                  if (foundModel) {
                    bestModel = foundModel;
                    selectionMethod = 'best_model_id (from training agent)';
                    console.log('  ✅ Using best_model_id from training agent:', bestModelId);
                  } else {
                    console.warn(`  ⚠️ Best model ID ${bestModelId} not found in comparison models. Falling back to AUC-ROC.`);
                    selectionMethod = 'aucRoc (fallback - best_model_id not found)';
                  }
                }
                
                // Fallback: Find best model by aucRoc if best_model_id not found or not available
                if (selectionMethod.includes('fallback')) {
                  let bestScore = bestModel.aucRoc || 0;
                  for (const model of comparisonModels) {
                    const score = model.aucRoc || 0;
                    if (score > bestScore) {
                      bestScore = score;
                      bestModel = model;
                    }
                  }
                  console.log('  ℹ️ Selected by AUC-ROC (fallback):', bestModel.modelName, 'Score:', bestScore);
                }
                
                // Check if test metrics exist (indicates hold dataset was used)
                const hasTestMetrics = bestModel.testAccuracy !== undefined && bestModel.testAccuracy !== null;
                
                console.log('  ✅ Best Model Selected:', bestModel.modelName);
                console.log('  - Model ID:', bestModel.modelId);
                console.log('  - Selection Method:', selectionMethod);
                console.log('  - Best AUC-ROC:', bestModel.aucRoc || bestModel.testAucRoc || 0);
                console.log('  - Has Test Metrics (testAccuracy exists):', hasTestMetrics);
                
                // Store best model info for explainability extraction
                if (bestModel.modelName && bestModel.modelId) {
                  bestModelInfo = {
                    modelName: bestModel.modelName,
                    modelId: bestModel.modelId,
                  };
                  console.log('  ✅ Stored best model info for explainability extraction:', bestModelInfo);
                }
                
                if (hasTestMetrics) {
                  // Use test metrics (hold dataset was available)
                  const finalMetrics = {
                    accuracy: bestModel.testAccuracy ?? bestModel.accuracy ?? 0,
                    precision: bestModel.testPrecision ?? bestModel.precision ?? 0,
                    recall: bestModel.testRecall ?? bestModel.recall ?? 0,
                    f1Score: bestModel.testF1Score ?? bestModel.f1Score ?? 0,
                    aucRoc: bestModel.testAucRoc ?? bestModel.aucRoc ?? 0,
                    aucPr: bestModel.testAucPr ?? bestModel.aucPr ?? 0,
                    logLoss: bestModel.testLogLoss ?? bestModel.logLoss ?? 0,
                  };
                  
                  console.log('  ✅ Using Test Metrics (Hold Dataset Available)');
                  console.log('  - Final Metrics to Save:', finalMetrics);
                  
                  const modelValidationData = {
                    hasHoldDataset: true,
                    bestModel: {
                      modelName: bestModel.modelName || 'Unknown',
                      metrics: finalMetrics,
                    },
                  };
                  
                  updateModelValidation(modelValidationData);
                  
                  // Generate LLM writeup for model validation
                  console.log('  📝 Generating model validation writeup...');
                  try {
                    // Get data summary for context
                    const dataSummaryContent = documentationData.modelObjective?.dataSummary?.content || '';
                    
                    const writeupResponse = await fastApiService.generateModelValidationWriteup({
                      model_validation: modelValidationData,
                      data_summary: dataSummaryContent,
                    });
                    
                    if (writeupResponse.success && writeupResponse.writeup) {
                      console.log('  ✅ Model validation writeup generated');
                      updateModelValidation({
                        ...modelValidationData,
                        writeup: writeupResponse.writeup,
                      });
                    } else {
                      console.warn('  ⚠️ Failed to generate model validation writeup:', writeupResponse.error);
                    }
                  } catch (error) {
                    console.error('  ❌ Error generating model validation writeup:', error);
                  }
                } else {
                  // No test metrics - hold dataset was not used
                  console.log('  ℹ️ No Test Metrics Found - No Hold Dataset Was Used During Training');
                  updateModelValidation({
                    hasHoldDataset: false,
                    bestModel: {
                      modelName: '',
                      metrics: {
                        accuracy: 0,
                        precision: 0,
                        recall: 0,
                        f1Score: 0,
                        aucRoc: 0,
                        aucPr: 0,
                        logLoss: 0,
                      },
                    },
                  });
                }
              }
            }
          } catch (error: any) {
            console.error('  ❌ Failed to process model comparison data:', error);
            console.error('  - Error details:', error.message);
            updateModelValidation({
              hasHoldDataset: false,
              bestModel: {
                modelName: '',
                metrics: {
                  accuracy: 0,
                  precision: 0,
                  recall: 0,
                  f1Score: 0,
                  aucRoc: 0,
                  aucPr: 0,
                  logLoss: 0,
                },
              },
            });
          }
        } else {
          console.warn('  ⚠️ No target variable configured');
        }
      } else {
        console.error('  ❌ No dataset analysis found in sessionStorage!');
        console.log('  💡 Make sure you have uploaded a dataset in Step 1');
      }

      // 3.9 Model Selection Summary
      console.log('📘 Building Model Selection summary');
      let modelSelectionSummary = null;
      const cachedSummary = sessionStorage.getItem('model_selection_summary');
      const trainingResultsStr = sessionStorage.getItem('training_results');
      
      // Get target variable for bivariate analysis
      const datasetConfigStr = sessionStorage.getItem('dataset_config');
      let targetVariable: string | null = null;
      if (datasetConfigStr) {
        try {
          const datasetConfig = JSON.parse(datasetConfigStr);
          targetVariable = datasetConfig.target_variable || null;
        } catch (e) {
          console.warn('  ⚠️ Failed to parse dataset config for target variable:', e);
        }
      }

      if (cachedSummary) {
        try {
          modelSelectionSummary = JSON.parse(cachedSummary);
          console.log('  ✅ Loaded cached model selection summary');
        } catch (error) {
          console.warn('  ⚠️ Failed to parse cached model selection summary. Will rebuild.', error);
        }
      }

      if (!modelSelectionSummary && trainingResultsStr) {
        try {
          const trainingResults = JSON.parse(trainingResultsStr);
          modelSelectionSummary = buildModelSelectionSummary(trainingResults);
          console.log('  ✅ Model selection summary generated from training results');
        } catch (error) {
          console.error('  ❌ Failed to build model selection summary from training results:', error);
        }
      }
      
      // Fetch variable analysis data from MessageState (separate from training results)
      if (modelSelectionSummary && datasetId) {
        try {
          console.log('  📊 Fetching variable analysis data from MessageState...');
          const variableAnalysisResponse = await fastApiService.getVariableAnalysis(datasetId);
          
          if (variableAnalysisResponse.success && variableAnalysisResponse.variable_statistics) {
            const usedFeatures = modelSelectionSummary.finalVariables.totalCount > 0 
              ? (trainingResultsStr ? JSON.parse(trainingResultsStr).used_features || JSON.parse(trainingResultsStr).usedFeatures || [] : [])
              : [];
            
            if (usedFeatures.length > 0 && variableAnalysisResponse.variable_statistics.length > 0) {
              // Filter variable statistics to only include used features
              const usedFeaturesSet = new Set(usedFeatures.map((f: string) => f.toLowerCase()));
              const filteredStats = variableAnalysisResponse.variable_statistics.filter((stat: any) => {
                const varName = stat.variable || stat.Variable || '';
                return usedFeaturesSet.has(varName.toLowerCase());
              });
              
              // Generate interpretation for each variable
              const variableAnalysisWithInterpretation = filteredStats.map((stat: any) => {
                const absCorr = Math.abs(stat.correlation || 0);
                const vif = stat.vif;
                const iv = stat.iv;
                
                const interpretations: string[] = [];
                if (absCorr > 0.8) {
                  interpretations.push('Strong correlation');
                } else if (absCorr < 0.1) {
                  interpretations.push('Weak correlation');
                }
                if (vif && vif > 10) {
                  interpretations.push('High VIF');
                }
                if (iv !== null && iv !== undefined && iv >= 0.3) {
                  interpretations.push('Strong IV');
                }
                
                return {
                  variable: stat.variable || stat.Variable || '',
                  correlation: stat.correlation !== null && stat.correlation !== undefined ? stat.correlation : null,
                  vif: stat.vif !== null && stat.vif !== undefined ? stat.vif : null,
                  iv: stat.iv !== null && stat.iv !== undefined ? stat.iv : null,
                  interpretation: interpretations.length > 0 ? interpretations.join(', ') : 'Normal',
                };
              });
              
              if (variableAnalysisWithInterpretation.length > 0) {
                modelSelectionSummary.finalVariables.variableAnalysis = variableAnalysisWithInterpretation;
                modelSelectionSummary.finalVariables.rowsToShow = modelSelectionSummary.finalVariables.rowsToShow || 20;
                console.log(`  ✅ Added variable analysis data for ${variableAnalysisWithInterpretation.length} used features`);
              } else {
                console.warn('  ⚠️ No matching variable statistics found for used features');
              }
            } else {
              console.warn('  ⚠️ Missing used features or variable statistics');
            }
          } else {
            console.warn('  ⚠️ Variable analysis data not available in MessageState');
          }
        } catch (error) {
          console.error('  ❌ Failed to fetch variable analysis data:', error);
        }
        
        // Fetch bivariate analysis charts for used_features
        if (modelSelectionSummary && datasetId && targetVariable) {
          try {
            console.log('  📊 Fetching bivariate analysis charts for used features...');
            const usedFeaturesForCharts = modelSelectionSummary.finalVariables.variableAnalysis 
              ? modelSelectionSummary.finalVariables.variableAnalysis.map(stat => stat.variable)
              : (trainingResultsStr ? JSON.parse(trainingResultsStr).used_features || JSON.parse(trainingResultsStr).usedFeatures || [] : []);
            
            if (usedFeaturesForCharts.length > 0) {
              // Fetch bivariate analysis for all variables first
              const allBivariateResults = await bivariateAnalysisService.analyzeAllVariables({
                dataset_id: datasetId,
                target_variable: targetVariable,
                binning_method: 'quantile',
                top_categories: 10,
                bins: 10
              });
              
              // Filter to only used_features and fetch individual chart data
              const bivariateCharts: Array<{
                variable_name: string;
                variable_type: 'categorical' | 'numerical';
                visualization_data: any;
              }> = [];
              
              for (const varName of usedFeaturesForCharts) {
                try {
                  const varAnalysis = await bivariateAnalysisService.getVariableAnalysis(
                    datasetId,
                    varName,
                    targetVariable
                  );
                  
                  if (varAnalysis && varAnalysis.analysis_result?.analysis_result?.visualization_data) {
                    bivariateCharts.push({
                      variable_name: varName,
                      variable_type: varAnalysis.analysis_result.variable_type as 'categorical' | 'numerical',
                      visualization_data: varAnalysis.analysis_result.analysis_result.visualization_data,
                    });
                  }
                } catch (varError) {
                  console.warn(`  ⚠️ Failed to fetch bivariate chart for ${varName}:`, varError);
                }
              }
              
              if (bivariateCharts.length > 0) {
                modelSelectionSummary.finalVariables.bivariateAnalysisCharts = {
                  charts: bivariateCharts,
                  variableCount: 4, // Default to 4 charts
                  selectedVariables: undefined,
                };
                console.log(`  ✅ Added bivariate analysis charts for ${bivariateCharts.length} used features`);
              } else {
                console.warn('  ⚠️ No bivariate charts generated for used features');
              }
            } else {
              console.warn('  ⚠️ No used features available for bivariate analysis');
            }
          } catch (error) {
            console.error('  ❌ Failed to fetch bivariate analysis charts:', error);
          }
        }
      }

      if (!modelSelectionSummary) {
        modelSelectionSummary = getDefaultModelSelectionSummary();
        console.log('  ℹ️ Using default model selection summary');
      }

      // Update model selection with all data (including bivariate charts)
      updateModelSelection({
        ...modelSelectionSummary,
        metadata: {
          ...modelSelectionSummary.metadata,
          generatedAt: new Date().toISOString(),
        },
      });

      // 4. Collect Model Owner Data
      console.log('📊 Collecting Model Owner Data:');
      const createdOn = new Date().toISOString();
      const createdBy = user?.name || 'Unknown User';
      console.log('  - Created By:', createdBy);
      console.log('  - Created On:', createdOn);
      
      updateModelOwner({
        createdBy: createdBy,
        createdOn: createdOn,
        approvedBy: '', // Empty by default, user can edit
      });

      // 5. Collect Model Performance Data
      console.log('📊 Collecting Model Performance Data:');
      try {
        // Parse dataset analysis and config
        const datasetAnalysisStr = sessionStorage.getItem('dataset_analysis');
        const datasetConfigStr = sessionStorage.getItem('dataset_config');
        const knowledgeGraphStr = sessionStorage.getItem('knowledge_graph_result');
        
        let datasetAnalysis: any = null;
        let datasetConfig: any = null;
        let knowledgeGraphResult: any = null;
        
        if (datasetAnalysisStr) {
          datasetAnalysis = JSON.parse(datasetAnalysisStr);
        }
        if (datasetConfigStr) {
          datasetConfig = JSON.parse(datasetConfigStr);
        }
        if (knowledgeGraphStr) {
          knowledgeGraphResult = JSON.parse(knowledgeGraphStr);
        }
        
        // Get dataset ID
        const datasetId = datasetAnalysis?.dataset_id || sessionStorage.getItem('dataset_id') || '';
        console.log('  - Dataset ID:', datasetId);
        
        // Get best model ID from model comparison data
        const modelComparisonDataStr = sessionStorage.getItem('model_comparison_data');
        let bestModelId = '';
        
        if (modelComparisonDataStr) {
          const comparisonModels = JSON.parse(modelComparisonDataStr);
          console.log('  - Model Comparison Data: Found', comparisonModels.length, 'models');
          if (comparisonModels.length > 0) {
            // Find best model by AUC-ROC
            const bestModel = comparisonModels.reduce((best: any, current: any) => {
              return (current.aucRoc || 0) > (best.aucRoc || 0) ? current : best;
            });
            bestModelId = bestModel.modelId || '';
            console.log('  - Best Model ID:', bestModelId);
            console.log('  - Best Model Name:', bestModel.modelName);
            console.log('  - Best Model AUC-ROC:', bestModel.aucRoc);
          } else {
            console.warn('  ⚠️ No models in comparison data');
          }
        } else {
          console.warn('  ⚠️ No model comparison data found in sessionStorage');
        }
        
        if (bestModelId && datasetId) {
          // Get data dictionary
          const dataDictionary = datasetConfig?.data_dictionary || null;
          
          // Get variable categories from knowledge graph
          let variableCategories: Record<string, string> = {};
          let categoryColors: Record<string, string> = {};
          
          // Try to get from stored knowledge graph result
          if (knowledgeGraphResult) {
            // Method 1: If nodes array is available, build mapping from nodes
            if (knowledgeGraphResult.nodes && Array.isArray(knowledgeGraphResult.nodes)) {
              knowledgeGraphResult.nodes.forEach((node: any) => {
                // Only process variable nodes (not category nodes)
                if (node.id && node.group && node.group !== 'category') {
                  variableCategories[node.id] = node.group;
                }
              });
              
              // Get colors from categories array if available
              if (knowledgeGraphResult.categories && Array.isArray(knowledgeGraphResult.categories)) {
                knowledgeGraphResult.categories.forEach((cat: any) => {
                  if (cat.name && cat.color) {
                    categoryColors[cat.name] = cat.color;
                  }
                });
              }
            }
            
            // Method 2: If variableCategoryDistribution is available, we still need nodes for mapping
            // But we can get colors from it
            if (knowledgeGraphResult.variableCategoryDistribution?.colors) {
              categoryColors = {
                ...categoryColors,
                ...knowledgeGraphResult.variableCategoryDistribution.colors
              };
            }
            
            // If we still don't have variable categories, try to fetch from backend
            if (Object.keys(variableCategories).length === 0) {
              console.log('  - No variable categories from stored result, fetching from backend...');
              try {
                const kgProgress = await fastApiService.pollKnowledgeGraphProgress(datasetId);
                if (kgProgress?.result?.nodes && Array.isArray(kgProgress.result.nodes)) {
                  kgProgress.result.nodes.forEach((node: any) => {
                    if (node.id && node.group && node.group !== 'category') {
                      variableCategories[node.id] = node.group;
                    }
                  });
                  
                  // Get colors from categories
                  if (kgProgress.result.categories && Array.isArray(kgProgress.result.categories)) {
                    kgProgress.result.categories.forEach((cat: any) => {
                      if (cat.name && cat.color) {
                        categoryColors[cat.name] = cat.color;
                      }
                    });
                  }
                }
              } catch (error) {
                console.warn('  ⚠️ Failed to fetch knowledge graph from backend:', error);
              }
            }
            
            console.log('  - Variable Categories:', Object.keys(variableCategories).length, 'features categorized');
            console.log('  - Category Colors:', Object.keys(categoryColors).length, 'categories with colors');
            if (Object.keys(variableCategories).length > 0) {
              console.log('  - Sample mappings:', Object.entries(variableCategories).slice(0, 5));
            }
          }
          
          // Call API to get model performance data
          console.log('  - Calling API to get model performance data...');
          console.log('    - Model ID:', bestModelId);
          console.log('    - Dataset ID:', datasetId);
          console.log('    - Has Data Dictionary:', !!dataDictionary);
          console.log('    - Variable Categories Count:', Object.keys(variableCategories).length);
          
          try {
            const performanceResult = await fastApiService.getModelPerformance({
              model_id: bestModelId,
              dataset_id: datasetId,
              data_dictionary: dataDictionary || undefined,
              variable_categories: variableCategories,
              category_colors: categoryColors,
            });
            
            if (performanceResult.success) {
              console.log('  ✅ Model Performance Data Retrieved:');
              console.log('    - Total Features:', performanceResult.total_features);
              console.log('    - Top Features:', performanceResult.top_features.length);
              console.log('    - Category Distribution:', Object.keys(performanceResult.category_distribution).length, 'categories');
              
              // Extract ROC curves, radar charts, and confusion matrices from model comparison data
              let rocCurves: { train: any[]; test: any[] } | undefined = undefined;
              let radarCharts: { train: any[]; test: any[] } | undefined = undefined;
              let confusionMatrices: any[] | undefined = undefined;

              try {
                const modelComparisonDataStr = sessionStorage.getItem('model_comparison_data');
                if (modelComparisonDataStr) {
                  const comparisonModels = JSON.parse(modelComparisonDataStr);
                  
                  // Extract ROC curves
                  console.log('  🔍 Extracting ROC curves from comparison models...');
                  console.log(`    - Total models: ${comparisonModels.length}`);
                  
                  const trainRocModels = comparisonModels
                    .filter((m: any) => {
                      const hasData = m.rocDataTrain && 
                                     Array.isArray(m.rocDataTrain.fpr) && 
                                     Array.isArray(m.rocDataTrain.tpr) &&
                                     m.rocDataTrain.fpr.length > 0 &&
                                     m.rocDataTrain.tpr.length > 0;
                      if (!hasData) {
                        console.log(`    - Model ${m.modelName}: No train ROC data (has rocDataTrain: ${!!m.rocDataTrain})`);
                      }
                      return hasData;
                    })
                    .map((m: any) => {
                      console.log(`    ✅ Model ${m.modelName}: Found train ROC data (fpr: ${m.rocDataTrain.fpr.length}, tpr: ${m.rocDataTrain.tpr.length})`);
                      return {
                        modelName: m.modelName,
                        modelId: `${m.modelId}-train`,
                        rocData: {
                          fpr: m.rocDataTrain.fpr,
                          tpr: m.rocDataTrain.tpr,
                          thresholds: m.rocDataTrain.thresholds || [],
                          auc: m.trainAucRoc || m.rocDataTrain.auc || 0,
                        },
                        color: m.color,
                      };
                    });

                  const testRocModels = comparisonModels
                    .filter((m: any) => {
                      const hasData = m.rocData && 
                                     Array.isArray(m.rocData.fpr) && 
                                     Array.isArray(m.rocData.tpr) &&
                                     m.rocData.fpr.length > 0 &&
                                     m.rocData.tpr.length > 0;
                      if (!hasData) {
                        console.log(`    - Model ${m.modelName}: No test ROC data (has rocData: ${!!m.rocData})`);
                      }
                      return hasData;
                    })
                    .map((m: any) => {
                      console.log(`    ✅ Model ${m.modelName}: Found test ROC data (fpr: ${m.rocData.fpr.length}, tpr: ${m.rocData.tpr.length})`);
                      return {
                        modelName: m.modelName,
                        modelId: `${m.modelId}-test`,
                        rocData: {
                          fpr: m.rocData.fpr,
                          tpr: m.rocData.tpr,
                          thresholds: m.rocData.thresholds || [],
                          auc: m.testAucRoc || m.aucRoc || m.rocData.auc || 0,
                        },
                        color: m.color,
                      };
                    });

                  console.log(`    - Train ROC models found: ${trainRocModels.length}`);
                  console.log(`    - Test ROC models found: ${testRocModels.length}`);

                  if (trainRocModels.length > 0 || testRocModels.length > 0) {
                    rocCurves = {
                      train: trainRocModels,
                      test: testRocModels,
                    };
                    console.log('  ✅ ROC curves extracted successfully');
                  } else {
                    console.log('  ⚠️ No ROC curves found in comparison models');
                  }

                  // Extract radar chart data
                  const trainRadarModels = comparisonModels
                    .filter((m: any) => m.trainAccuracy !== undefined || m.accuracy !== undefined)
                    .map((m: any) => ({
                      modelName: m.modelName,
                      modelId: `${m.modelId}-train`,
                      accuracy: m.trainAccuracy ?? m.accuracy ?? 0,
                      precision: m.trainPrecision ?? m.precision ?? 0,
                      recall: m.trainRecall ?? m.recall ?? 0,
                      f1Score: m.trainF1Score ?? m.f1Score ?? 0,
                      aucRoc: m.trainAucRoc ?? m.aucRoc ?? 0,
                      color: m.color,
                    }));

                  const testRadarModels = comparisonModels
                    .filter((m: any) => m.testAccuracy !== undefined || m.accuracy !== undefined)
                    .map((m: any) => ({
                      modelName: m.modelName,
                      modelId: `${m.modelId}-test`,
                      accuracy: m.testAccuracy ?? m.accuracy ?? 0,
                      precision: m.testPrecision ?? m.precision ?? 0,
                      recall: m.testRecall ?? m.recall ?? 0,
                      f1Score: m.testF1Score ?? m.f1Score ?? 0,
                      aucRoc: m.testAucRoc ?? m.aucRoc ?? 0,
                      color: m.color,
                    }));

                  if (trainRadarModels.length > 0 || testRadarModels.length > 0) {
                    radarCharts = {
                      train: trainRadarModels,
                      test: testRadarModels,
                    };
                  }

                  // Extract confusion matrices
                  const confusionMatrixModels = comparisonModels
                    .filter((m: any) => m.confusionMatrix || m.testConfusionMatrix)
                    .map((m: any) => ({
                      modelName: m.modelName,
                      modelId: m.modelId,
                      matrix: m.testConfusionMatrix || m.confusionMatrix,
                      trainMatrix: m.trainConfusionMatrix,
                      accuracy: m.testAccuracy ?? m.accuracy ?? 0,
                      trainAccuracy: m.trainAccuracy,
                      f1Score: m.testF1Score ?? m.f1Score ?? 0,
                      trainF1Score: m.trainF1Score,
                      color: m.color,
                    }));

                  if (confusionMatrixModels.length > 0) {
                    confusionMatrices = confusionMatrixModels;
                  }

                  console.log('  ✅ Extracted model comparison charts:');
                  console.log(`    - ROC Curves: Train=${trainRocModels.length}, Test=${testRocModels.length}`);
                  console.log(`    - Radar Charts: Train=${trainRadarModels.length}, Test=${testRadarModels.length}`);
                  console.log(`    - Confusion Matrices: ${confusionMatrixModels.length}`);
                }
              } catch (error) {
                console.warn('  ⚠️ Failed to extract model comparison charts:', error);
              }

              // Extract monotonicity data for each model
              let monotonicityData: Array<{
                modelName: string;
                modelId: string;
                monotonicityScore: number;
                ksStatistic: number;
                ksThreshold: number;
                liftTopDecile: number | null;
                overallBadRate: number;
                auc: number;
                gini: number;
                violations: Array<{ fromDecile: number; toDecile: number; drop: number; }>;
                deciles: Array<Record<string, any>>;
              }> = [];

              try {
                console.log('  🔍 Extracting monotonicity data from model evaluations...');
                const modelComparisonDataStr = sessionStorage.getItem('model_comparison_data');
                if (modelComparisonDataStr) {
                  const comparisonModels = JSON.parse(modelComparisonDataStr);
                  
                  // Fetch monotonicity data for each model
                  const monotonicityPromises = comparisonModels.map(async (model: any) => {
                    try {
                      const evaluationResponse = await modelEvaluationService.getModelEvaluation(model.modelId, true);
                      const monotonicity = evaluationResponse.evaluation_data?.monotonicity_results || 
                                         evaluationResponse.evaluation_data?.performance_metrics?.monotonicity_results;
                      
                      if (monotonicity) {
                        console.log(`    ✅ Model ${model.modelName}: Found monotonicity data`);
                        
                        // Extract PSI data
                        let psiData: { value: number; status: 'Stable' | 'Moderate' | 'Significant'; interpretation: string } | undefined = undefined;
                        if (monotonicity.psi !== undefined && monotonicity.psi !== null) {
                          const psiValue = Number(monotonicity.psi);
                          let status: 'Stable' | 'Moderate' | 'Significant';
                          let interpretation: string;
                          
                          if (psiValue < 0.1) {
                            status = 'Stable';
                            interpretation = 'No significant population shift - Model is stable';
                          } else if (psiValue < 0.25) {
                            status = 'Moderate';
                            interpretation = 'Moderate population shift - Monitor closely';
                          } else {
                            status = 'Significant';
                            interpretation = 'Significant population shift - Investigate and recalibrate';
                          }
                          
                          psiData = { value: psiValue, status, interpretation };
                          console.log(`    ✅ Model ${model.modelName}: Found PSI data (${psiValue.toFixed(4)})`);
                        }
                        
                        // Extract CSI data
                        let csiData: Array<{ variable: string; csiValue: number; status: 'Stable' | 'Moderate' | 'Significant' }> | undefined = undefined;
                        if (monotonicity.csi && Array.isArray(monotonicity.csi) && monotonicity.csi.length > 0) {
                          csiData = monotonicity.csi.map((row: any) => {
                            const csiValue = Number(row.CSI || row.csi || 0);
                            let status: 'Stable' | 'Moderate' | 'Significant';
                            
                            if (csiValue < 0.1) {
                              status = 'Stable';
                            } else if (csiValue < 0.25) {
                              status = 'Moderate';
                            } else {
                              status = 'Significant';
                            }
                            
                            return {
                              variable: row.Variable || row.variable || '',
                              csiValue: csiValue,
                              status: row.Status || status,
                            };
                          }).filter((item: any) => item.variable); // Filter out empty variables
                          
                          console.log(`    ✅ Model ${model.modelName}: Found CSI data for ${csiData.length} variables`);
                        }
                        
                        return {
                          modelName: model.modelName,
                          modelId: model.modelId,
                          monotonicityScore: (monotonicity.monotonicity_score || 0) * 100, // Convert to percentage
                          ksStatistic: monotonicity.ks || 0,
                          ksThreshold: monotonicity.ks_threshold || 0,
                          liftTopDecile: monotonicity.lift_top_decile ?? null,
                          overallBadRate: monotonicity.overall_bad_rate || 0,
                          auc: monotonicity.auc || 0,
                          gini: monotonicity.gini || 0,
                          violations: (monotonicity.monotonicity_violations || []).map((v: any) => ({
                            fromDecile: v.from_decile,
                            toDecile: v.to_decile,
                            drop: v.drop,
                          })),
                          deciles: monotonicity.deciles || [],
                          psi: psiData,
                          csi: csiData,
                        };
                      } else {
                        console.log(`    - Model ${model.modelName}: No monotonicity data available`);
                        return null;
                      }
                    } catch (error) {
                      console.warn(`    ⚠️ Failed to fetch monotonicity for model ${model.modelName}:`, error);
                      return null;
                    }
                  });

                  const results = await Promise.all(monotonicityPromises);
                  monotonicityData = results.filter((r): r is NonNullable<typeof r> => r !== null);
                  
                  console.log(`    - Monotonicity data found for ${monotonicityData.length} out of ${comparisonModels.length} models`);
                  
                  // Generate LLM write-ups for decile progression for each model
                  if (monotonicityData.length > 0) {
                    console.log('  📝 Generating decile progression write-ups...');
                    const writeupPromises = monotonicityData.map(async (monoData) => {
                      try {
                        const writeupResponse = await fastApiService.generateDecileProgressionWriteup({
                          model_name: monoData.modelName,
                          deciles: monoData.deciles,
                          monotonicity_score: monoData.monotonicityScore,
                          violations: monoData.violations,
                        });
                        if (writeupResponse.success && writeupResponse.writeup) {
                          console.log(`    ✅ Generated write-up for ${monoData.modelName}`);
                          return { ...monoData, decileProgressionWriteup: writeupResponse.writeup };
                        } else {
                          console.warn(`    ⚠️ Failed to generate write-up for ${monoData.modelName}`);
                          return monoData;
                        }
                      } catch (error) {
                        console.warn(`    ⚠️ Error generating write-up for ${monoData.modelName}:`, error);
                        return monoData;
                      }
                    });
                    
                    monotonicityData = await Promise.all(writeupPromises);
                    console.log('  ✅ Decile progression write-ups generated');
                    
                    // Generate monotonicity summary writeup
                    console.log('  📝 Generating monotonicity summary writeup...');
                    const shouldGenerateSummary = !documentationData.modelPerformance.monotonicitySummary?.writeup ||
                      documentationData.modelPerformance.monotonicitySummary?.lastGenerated === null;
                    
                    if (shouldGenerateSummary && monotonicityData.length > 0) {
                      try {
                        const summaryResponse = await fastApiService.generateMonotonicitySummary({
                          models: monotonicityData.map(mono => ({
                            modelName: mono.modelName,
                            monotonicityScore: mono.monotonicityScore,
                            ksStatistic: mono.ksStatistic,
                            liftTopDecile: mono.liftTopDecile,
                            auc: mono.auc,
                            gini: mono.gini,
                            psi: mono.psi,
                          })),
                        });
                        
                        if (summaryResponse.success && summaryResponse.writeup) {
                          console.log('  ✅ Generated monotonicity summary writeup');
                          updateModelPerformance({
                            monotonicitySummary: {
                              writeup: summaryResponse.writeup,
                              lastGenerated: new Date().toISOString(),
                            },
                          });
                        } else {
                          console.warn('  ⚠️ Failed to generate monotonicity summary writeup:', summaryResponse.error);
                        }
                      } catch (error) {
                        console.warn('  ⚠️ Error generating monotonicity summary writeup:', error);
                      }
                    } else {
                      console.log('  - Using existing monotonicity summary writeup');
                    }
                  }
                }
              } catch (error) {
                console.warn('  ⚠️ Failed to extract monotonicity data:', error);
              }

              // Extract granular accuracy data for all variables
              let granularAccuracyData: {
                variables: Array<{
                  variableName: string;
                  segments: Array<{
                    segment: string;
                    accuracy: number;
                    precision: number;
                    recall: number;
                    f1Score: number;
                  }>;
                }>;
                variablesToShow: number;
              } | undefined = undefined;

              try {
                console.log('  🔍 Extracting granular accuracy data from model evaluations...');
                const modelComparisonDataStr = sessionStorage.getItem('model_comparison_data');
                if (modelComparisonDataStr) {
                  const comparisonModels = JSON.parse(modelComparisonDataStr);
                  
                  // Fetch granular accuracy data for each model
                  const allGranularData: Array<{
                    variable: string;
                    segment: string;
                    accuracy: number;
                    precision: number;
                    recall: number;
                    f1_score: number;
                  }> = [];

                  const granularPromises = comparisonModels.map(async (model: any) => {
                    try {
                      const evaluationResponse = await modelEvaluationService.getModelEvaluation(model.modelId, true);
                      const granularData = evaluationResponse.evaluation_data?.granular_accuracy || [];
                      
                      if (granularData && granularData.length > 0) {
                        console.log(`    ✅ Model ${model.modelName}: Found ${granularData.length} granular accuracy records`);
                        granularData.forEach((item: any) => {
                          allGranularData.push({
                            variable: item.variable || 'Unknown',
                            segment: String(item.segment || 'Unknown'),
                            accuracy: item.accuracy || 0,
                            precision: item.precision || 0,
                            recall: item.recall || 0,
                            f1_score: item.f1_score || 0,
                          });
                        });
                      } else {
                        console.log(`    - Model ${model.modelName}: No granular accuracy data available`);
                      }
                    } catch (error) {
                      console.warn(`    ⚠️ Failed to fetch granular accuracy for model ${model.modelName}:`, error);
                    }
                  });

                  await Promise.all(granularPromises);
                  
                  if (allGranularData.length > 0) {
                    // Group by variable, then by segment
                    const variableMap = new Map<string, Map<string, Array<{
                      accuracy: number;
                      precision: number;
                      recall: number;
                      f1_score: number;
                    }>>>();

                    allGranularData.forEach(item => {
                      if (!variableMap.has(item.variable)) {
                        variableMap.set(item.variable, new Map());
                      }
                      const segmentMap = variableMap.get(item.variable)!;
                      if (!segmentMap.has(item.segment)) {
                        segmentMap.set(item.segment, []);
                      }
                      segmentMap.get(item.segment)!.push({
                        accuracy: item.accuracy,
                        precision: item.precision,
                        recall: item.recall,
                        f1_score: item.f1_score,
                      });
                    });

                    // Calculate averages for each variable-segment combination
                    const variables: Array<{
                      variableName: string;
                      segments: Array<{
                        segment: string;
                        accuracy: number;
                        precision: number;
                        recall: number;
                        f1Score: number;
                      }>;
                    }> = [];

                    variableMap.forEach((segmentMap, variableName) => {
                      const segments: Array<{
                        segment: string;
                        accuracy: number;
                        precision: number;
                        recall: number;
                        f1Score: number;
                      }> = [];

                      segmentMap.forEach((items, segment) => {
                        const count = items.length;
                        const avgAccuracy = items.reduce((sum, item) => sum + item.accuracy, 0) / count;
                        const avgPrecision = items.reduce((sum, item) => sum + item.precision, 0) / count;
                        const avgRecall = items.reduce((sum, item) => sum + item.recall, 0) / count;
                        const avgF1Score = items.reduce((sum, item) => sum + item.f1_score, 0) / count;

                        segments.push({
                          segment,
                          accuracy: avgAccuracy,
                          precision: avgPrecision,
                          recall: avgRecall,
                          f1Score: avgF1Score,
                        });
                      });

                      // Sort segments by segment number if possible
                      segments.sort((a, b) => {
                        const aMatch = a.segment.match(/Segment\s+(\d+)/i);
                        const bMatch = b.segment.match(/Segment\s+(\d+)/i);
                        if (aMatch && bMatch) {
                          return parseInt(aMatch[1]) - parseInt(bMatch[1]);
                        }
                        return a.segment.localeCompare(b.segment);
                      });

                      variables.push({
                        variableName,
                        segments,
                      });
                    });

                    // Sort variables alphabetically
                    variables.sort((a, b) => a.variableName.localeCompare(b.variableName));

                    granularAccuracyData = {
                      variables,
                      variablesToShow: 5, // Default value
                    };

                    console.log(`    - Granular accuracy data found for ${variables.length} variables`);
                    console.log(`    - Total segments across all variables: ${allGranularData.length}`);
                  } else {
                    console.log('    - No granular accuracy data found in any model');
                  }
                }
              } catch (error) {
                console.warn('  ⚠️ Failed to extract granular accuracy data:', error);
              }

              // Extract explainability data (SHAP and PDP) for best performing model
              let explainabilityData: {
                shap?: {
                  beeswarm?: {
                    data: Array<{
                      featureName: string;
                      values: number[];
                      feature_values?: number[];
                      original_feature_values?: number[];
                      mean_abs?: number;
                      original_feature_name?: string;
                    }>;
                    featureCount: number | 'all';
                  };
                  waterfall?: {
                    data: Array<{
                      feature: string;
                      feature_value: number;
                      shap_value: number;
                    }>;
                    baseValue: number;
                    featureCount: number | 'all';
                  };
                };
                pdp?: {
                  data: Array<{
                    feature_name: string;
                    values: Array<{ x: number; y: number }>;
                    ice_lines?: number[][];
                  }>;
                  featureCount: number | 'all';
                  maxIceLines: number;
                };
                writeup?: {
                  content: string;
                  lastGenerated: string;
                };
              } | undefined = undefined;

              try {
                console.log('  🔍 Extracting explainability data for best performing model...');
                
                // Use best model info from current generation (not from context which may be stale)
                if (!bestModelInfo || !bestModelInfo.modelName || !bestModelInfo.modelId) {
                  // Fallback: try to get from context if not available in current generation
                  const bestModelName = documentationData.modelDesign.modelValidation.bestModel.modelName;
                  if (!bestModelName) {
                    console.log('    - No best model found, skipping explainability data');
                  } else {
                    // Find best model ID from comparison models
                    const modelComparisonDataStr = sessionStorage.getItem('model_comparison_data');
                    if (modelComparisonDataStr) {
                      const comparisonModels = JSON.parse(modelComparisonDataStr);
                      const bestModel = comparisonModels.find((m: any) => m.modelName === bestModelName);
                      
                      if (bestModel && bestModel.modelId) {
                        bestModelInfo = {
                          modelName: bestModel.modelName,
                          modelId: bestModel.modelId,
                        };
                        console.log(`    - Using best model from context: ${bestModelInfo.modelName} (ID: ${bestModelInfo.modelId})`);
                      }
                    }
                  }
                }
                
                if (bestModelInfo && bestModelInfo.modelName && bestModelInfo.modelId) {
                  console.log(`    - Best Model: ${bestModelInfo.modelName} (ID: ${bestModelInfo.modelId})`);
                  
                  // Fetch full evaluation data for best model
                  const evaluationResponse = await modelEvaluationService.getModelEvaluation(bestModelInfo.modelId, true);
                  const evalData = evaluationResponse.evaluation_data;
                  
                  if (evalData && evalData.explainability_data) {
                    // Extract SHAP beeswarm data
                    const shapBeeswarmEntries = evalData.explainability_data.filter(
                      (d: any) => d.data_type === 'shap_summary' && d.feature_name
                    );
                    
                    const beeswarmData = shapBeeswarmEntries.map((entry: any) => ({
                      featureName: entry.feature_name || 'Unknown',
                      values: Array.isArray(entry.values) ? entry.values : [],
                      feature_values: entry.metadata?.feature_values,
                      original_feature_values: entry.metadata?.original_feature_values,
                      mean_abs: entry.metadata?.mean_abs || 0,
                      original_feature_name: entry.metadata?.original_feature_name,
                    })).sort((a: any, b: any) => Math.abs(b.mean_abs || 0) - Math.abs(a.mean_abs || 0));
                    
                    // Extract SHAP waterfall data
                    let waterfallData: Array<{ feature: string; feature_value: number; shap_value: number }> = [];
                    let baseValue = 0;
                    
                    const waterfallEntry = evalData.explainability_data.find(
                      (d: any) => d.data_type === 'shap_waterfall'
                    );
                    
                    if (waterfallEntry && waterfallEntry.values && Array.isArray(waterfallEntry.values)) {
                      waterfallData = waterfallEntry.values;
                      baseValue = waterfallEntry.metadata?.base_value || 0;
                    } else {
                      // Try to get from global shap_summary entry
                      const globalShapEntry = evalData.explainability_data.find(
                        (d: any) => d.data_type === 'shap_summary' && !d.feature_name
                      );
                      if (globalShapEntry && globalShapEntry.values) {
                        baseValue = globalShapEntry.values.base_value || 0;
                      }
                    }
                    
                    // Fetch PDP data using lazy-load endpoint (PDP data is not included in explainability_data)
                    let pdpData: Array<{
                      feature_name: string;
                      values: Array<{ x: number; y: number }>;
                      ice_lines: number[][];
                    }> = [];
                    
                    try {
                      console.log(`    - Fetching PDP data for model ${bestModelInfo.modelId}...`);
                      const pdpResponse = await modelEvaluationService.getPDPData(bestModelInfo.modelId, 'test');
                      
                      if (Array.isArray(pdpResponse) && pdpResponse.length > 0) {
                        console.log(`    - Fetched ${pdpResponse.length} PDP entries from lazy-load endpoint`);
                        
                        pdpData = pdpResponse.map((entry: any) => {
                          // Ensure values are in {x, y} format
                          let values: Array<{ x: number; y: number }> = [];
                          
                          // Handle different data structures
                          if (entry.values && Array.isArray(entry.values)) {
                            values = entry.values
                              .map((v: any) => {
                                if (typeof v === 'object' && v !== null && 'x' in v && 'y' in v) {
                                  return { x: Number(v.x), y: Number(v.y) };
                                }
                                return null;
                              })
                              .filter((v: any): v is { x: number; y: number } => v !== null);
                          } else if (entry.data_values) {
                            // Handle case where values are stored in data_values field
                            const parsedValues = typeof entry.data_values === 'string' 
                              ? JSON.parse(entry.data_values) 
                              : entry.data_values;
                            if (Array.isArray(parsedValues)) {
                              values = parsedValues
                                .map((v: any) => {
                                  if (typeof v === 'object' && v !== null && 'x' in v && 'y' in v) {
                                    return { x: Number(v.x), y: Number(v.y) };
                                  }
                                  return null;
                                })
                                .filter((v: any): v is { x: number; y: number } => v !== null);
                            }
                          }
                          
                          // Extract ICE lines from metadata
                          let iceLines: number[][] = [];
                          if (entry.metadata) {
                            const metadata = typeof entry.metadata === 'string' 
                              ? JSON.parse(entry.metadata) 
                              : entry.metadata;
                            iceLines = metadata.ice_lines || [];
                          }
                          
                          console.log(`      - PDP entry: ${entry.feature_name}, values: ${values.length}, ice_lines: ${iceLines.length}`);
                          
                          return {
                            feature_name: entry.feature_name || 'Unknown',
                            values,
                            ice_lines: iceLines,
                          };
                        });
                      } else {
                        console.log(`    - No PDP data found in lazy-load response`);
                      }
                    } catch (pdpError) {
                      console.error(`    ❌ Error fetching PDP data:`, pdpError);
                    }
                    
                    // Sort PDP by SHAP importance (if available)
                    const sortedPdpData = [...pdpData].sort((a, b) => {
                      const aShap = beeswarmData.find(d => d.featureName === a.feature_name);
                      const bShap = beeswarmData.find(d => d.featureName === b.feature_name);
                      const aImportance = aShap?.mean_abs || 0;
                      const bImportance = bShap?.mean_abs || 0;
                      return bImportance - aImportance;
                    });
                    
                    // Generate AI explainability write-up
                    let writeupContent: { content: string; lastGenerated: string } | undefined = undefined;
                    try {
                      console.log('    - Generating AI explainability write-up...');
                      const writeupResult = await fastApiService.generateAIExplainabilityWriteup({
                        beeswarm_data: beeswarmData,
                        waterfall_data: waterfallData,
                        pdp_data: sortedPdpData,
                      });
                      
                      if (writeupResult.success && writeupResult.writeup) {
                        writeupContent = {
                          content: writeupResult.writeup,
                          lastGenerated: new Date().toISOString(),
                        };
                        console.log('    ✅ AI explainability write-up generated');
                      } else {
                        console.warn('    ⚠️ Failed to generate AI explainability write-up:', writeupResult.error);
                      }
                    } catch (writeupError) {
                      console.error('    ❌ Error generating AI explainability write-up:', writeupError);
                    }
                    
                    explainabilityData = {
                      shap: {
                        beeswarm: {
                          data: beeswarmData,
                          featureCount: 'all', // Default to all, user can filter
                        },
                        waterfall: {
                          data: waterfallData,
                          baseValue,
                          featureCount: 'all', // Default to all, user can filter
                        },
                      },
                      pdp: {
                        data: sortedPdpData,
                        featureCount: 5, // Default 5
                        maxIceLines: 100, // Default 100
                      },
                      writeup: writeupContent,
                    };
                    
                    console.log(`    ✅ SHAP Beeswarm: ${beeswarmData.length} features`);
                    console.log(`    ✅ SHAP Waterfall: ${waterfallData.length} features, baseValue: ${baseValue}`);
                    console.log(`    ✅ PDP: ${sortedPdpData.length} features`);
                  } else {
                    console.log('    - No explainability data found for best model');
                  }
                } else {
                  console.log('    - No best model info available for explainability extraction');
                }
              } catch (error) {
                console.warn('  ⚠️ Failed to extract explainability data:', error);
                // Ensure explainabilityData is set to undefined if extraction fails
                // This prevents undefined reference errors
                if (!explainabilityData) {
                  explainabilityData = undefined;
                }
              }

              // Update model performance with all data including explainability
              // Ensure explainabilityData is always defined (even if undefined) to prevent errors
              try {
                updateModelPerformance({
                  features: {
                    totalCount: performanceResult.total_features,
                    usedFeatures: performanceResult.used_features,
                    topFeatures: performanceResult.top_features.map(f => ({
                      featureName: f.feature_name,
                      importance: f.importance,
                      description: f.description,
                    })),
                    topN: 20, // Default
                    categoryDistribution: performanceResult.category_distribution,
                    categoryColors: performanceResult.category_colors,
                  },
                  rocCurves,
                  radarCharts,
                  confusionMatrices,
                  monotonicity: monotonicityData.length > 0 ? monotonicityData : undefined,
                  granularAccuracy: granularAccuracyData,
                  explainability: explainabilityData, // Can be undefined if extraction failed
                });
              } catch (updateError) {
                console.error('  ❌ Error updating model performance:', updateError);
                // Try to update without explainability if the full update fails
                try {
                  updateModelPerformance({
                    features: {
                      totalCount: performanceResult.total_features,
                      usedFeatures: performanceResult.used_features,
                      topFeatures: performanceResult.top_features.map(f => ({
                        featureName: f.feature_name,
                        importance: f.importance,
                        description: f.description,
                      })),
                      topN: 20,
                      categoryDistribution: performanceResult.category_distribution,
                      categoryColors: performanceResult.category_colors,
                    },
                    rocCurves,
                    radarCharts,
                    confusionMatrices,
                    monotonicity: monotonicityData.length > 0 ? monotonicityData : undefined,
                    granularAccuracy: granularAccuracyData,
                    // Omit explainability if it causes issues
                  });
                } catch (fallbackError) {
                  console.error('  ❌ Fallback update also failed:', fallbackError);
                }
              }
            } else {
              console.warn('  ⚠️ Failed to get model performance data:', performanceResult.error);
              updateModelPerformance({
                features: {
                  totalCount: 0,
                  usedFeatures: [],
                  topFeatures: [],
                  topN: 20,
                  categoryDistribution: {},
                  categoryColors: {},
                },
              });
            }
          } catch (error) {
            console.error('  ❌ Error calling model performance API:', error);
            updateModelPerformance({
              features: {
                totalCount: 0,
                usedFeatures: [],
                topFeatures: [],
                topN: 20,
                categoryDistribution: {},
                categoryColors: {},
              },
            });
          }
        } else {
          console.warn('  ⚠️ No best model ID or dataset ID found. Skipping model performance data collection.');
          console.log('    - Best Model ID:', bestModelId || 'NOT FOUND');
          console.log('    - Dataset ID:', datasetId || 'NOT FOUND');
          updateModelPerformance({
            features: {
              totalCount: 0,
              usedFeatures: [],
              topFeatures: [],
              topN: 20,
              categoryDistribution: {},
              categoryColors: {},
            },
          });
        }
      } catch (error: any) {
        console.error('  ❌ Failed to collect model performance data:', error);
        updateModelPerformance({
          features: {
            totalCount: 0,
            usedFeatures: [],
            topFeatures: [],
            topN: 20,
            categoryDistribution: {},
            categoryColors: {},
          },
        });
      }

      // 6. Mark documentation as generated
      console.log('✅ Documentation generation complete! Showing documentation viewer...');
      generateDocumentation();
      setShowDocumentation(true);
      console.log('✅ showDocumentation set to true');
    } catch (error) {
      console.error('❌ Error generating documentation:', error);
      console.error('Error stack:', error instanceof Error ? error.stack : 'No stack trace');
      
      // Even if there's an error, try to show the documentation if we have some data
      // This prevents blank screens when partial data is available
      try {
        generateDocumentation();
        setShowDocumentation(true);
        console.log('✅ Attempted to show documentation despite error');
      } catch (stateError) {
        console.error('❌ Failed to update state after error:', stateError);
      }
      
      // Show a less intrusive error message
      console.warn('⚠️ Some sections may be incomplete. Please check the console for details.');
    } finally {
      setIsGenerating(false);
      console.log('✅ Documentation generation process finished (isGenerating set to false)');
    }
  };

  const handleDownloadDocumentation = async () => {
    setIsDownloading(true);
    try {
      const response = await fastApiService.downloadDocumentation(documentationData);
      
      // Create blob and download - backend sends a ZIP file containing DOCX and Excel files
      const blob = new Blob([response], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `model_documentation_${new Date().toISOString().split('T')[0]}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error downloading documentation:', error);
      alert('Failed to download documentation. Please try again.');
    } finally {
      setIsDownloading(false);
    }
  };

  const handleRefreshDocumentation = async () => {
    // Re-run the full documentation generation pipeline using the latest session state
    await handleGenerateDocumentation();
  };

  return (
    <div className="space-y-6 model-documentation">
      {!showDocumentation ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8">
          <div className="max-w-2xl mx-auto text-center space-y-6">
            <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
              <FileText className="h-10 w-10 text-blue-600" />
            </div>
            
            <div>
              <h3 className="text-2xl font-bold text-gray-900 mb-2">Generate Interactive Documentation</h3>
              <p className="text-gray-600">
                Create comprehensive model documentation from your analysis journey. 
                This will compile all results, insights, and summaries into an interactive report 
                that you can edit and export.
              </p>
          </div>
          
          <button
              onClick={handleGenerateDocumentation}
              disabled={isGenerating}
              className="px-6 py-3 bg-blue-600 dark:bg-[#292966] text-white dark:text-[#ccccff] rounded-lg hover:bg-blue-700 dark:hover:bg-[#333380] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center space-x-2 mx-auto"
            >
              {isGenerating ? (
                <>
                  <Loader className="h-5 w-5 animate-spin" />
                  <span>Generating Documentation...</span>
                </>
              ) : (
                <>
                  <FileText className="h-5 w-5" />
                  <span>Generate Documentation</span>
                </>
              )}
          </button>

            <p className="text-sm text-gray-500">
              This will collect data from your objectives, analysis, and model training steps.
            </p>
        </div>
      </div>
      ) : (
        <ErrorBoundary>
          <DocumentationViewer
            onDownload={handleDownloadDocumentation}
            onRefresh={handleRefreshDocumentation}
            isRefreshing={isGenerating}
            isDownloading={isDownloading}
          />
        </ErrorBoundary>
      )}

      {/* Chat Component */}
      {renderStepChat(9)}
    </div>
  );
};

export default Step9ModelDocumentation;
















