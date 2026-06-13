import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';
import { ModelSelectionSummary, getDefaultModelSelectionSummary } from '../utils/modelSelectionSummary';
import { optimizedSetItem, optimizedGetItem, optimizedRemoveItem } from '../utils/storageOptimization';

// Define the structure for storing documentation data
export interface DocumentationData {
  // Objectives Section
  objectives: {
    modelObjective: {
      description: string;
      problemStatement: string;
      generatedObjective: string; // LLM-generated 3-line objective text
      lastGenerated: string | null;
    };
    dataSummary: {
      content: string;
      metadata: {
        columns: string[];
        dataDictionary: string | null;
        lastGenerated: string | null;
      };
    };
  };
  
  // Model Design Section
  modelDesign: {
    dataOverview: {
      datasetStats: {
        totalRows: number;
        totalColumns: number;
        numericalColumns: number;
        categoricalColumns: number;
        dateColumns: number;
      };
      variableCategorization: {
        categories: Record<string, number>; // category name -> count
        colors: Record<string, string>; // category name -> color
        imageData: string | null; // base64 encoded pie chart image
      };
      dataQuality: {
        summary: string; // LLM-generated summary
        metrics: {
          emptyColumns: number;
          constantColumns: number;
          sparseColumns: number;
          formattingIssues: number;
          emptyColumnNames: string[];
          constantColumnNames: string[];
          sparseColumnNames: string[];
          formattingIssueColumnNames: string[];
        };
        recommendations: string[];
        lastGenerated: string | null;
      };
      edaReport?: {
        table: Array<{
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
        }>;
        rowsToShow: number;
      };
    };
    targetDefinition: {
      targetVariableName: string;
      definition: string; // From data dictionary or LLM-generated
      eventRate: {
        eventCount: number;
        totalCount: number;
        percentage: number;
      };
      lastGenerated: string | null;
    };
    samplingPlan: {
      hasSplit: boolean; // Whether data was split into dev/hold
      train: {
        total: number;
        eventCount: number;
        eventRate: number;
      };
      hold: {
        total: number;
        eventCount: number;
        eventRate: number;
      };
      samplingIdentifier: string;
      writeup?: string; // LLM-generated writeup
    };
    segmentation: {
      hasSegmentation: boolean;
      variablesUsed?: string[]; // Variables used for segmentation
      method?: string; // Segmentation method (e.g., "CART", "CHAID")
      segments: Array<{
        segmentNumber: number;
        rule: string;
        total: number;
        eventRate: number;
        segmentDistribution: number;
      }>;
      segmentSizesChart?: {
        labels: string[];
        data: number[];
        eventRates?: number[]; // Event rates for line chart (as decimals, 0-1)
        imageData?: string; // base64 encoded chart image
      };
      segmentProportionsChart?: {
        labels: string[];
        data: number[];
        colors?: string[];
        imageData?: string; // base64 encoded chart image
      };
      ivVisualizationCharts?: {
        ivReport?: {
          table: Array<{
            segment_id: number;
            accounts: number;
            bads: number;
            goods: number;
            bad_rate: number;
            dist_goods: number;
            dist_bads: number;
            woe: number;
            iv_contribution: number;
          }>;
          totals: {
            N: number;
            GT: number;
            BT: number;
            bad_rate: number;
            IV: number;
          };
          interpretation: {
            bucket: string;
          };
        };
        weightOfEvidenceChart?: {
          data: any;
          imageData?: string;
        };
        ivComponentsChart?: {
          data: any;
          imageData?: string;
        };
        goodBadDistributionChart?: {
          data: any;
          imageData?: string;
        };
        badRateChart?: {
          data: any;
          imageData?: string;
        };
        populationDistributionChart?: {
          data: any;
          imageData?: string;
        };
        ivStrength?: {
          value: number;
          label: string; // e.g., "Weak", "Moderate", "Strong"
        };
      };
      understanding?: {
        content: string; // LLM-generated explanation
        lastGenerated: string | null;
      };
    };
    dataTreatment: {
      qualityCheckPlan: {
        table: Array<{
          Issue: string;
          Variable: string;
          Observation: string;
          Treatment: string;
        }>;
        rowsToShow: number; // Default 20
      };
      implementedQualityChanges: {
        columnStats: Array<{
          Column: string;
          Type: string;
          Missing: number;
          Unique: number | string;
          Mean: number | string;
          Median: number | string;
          Mode: string | number;
          Std: number | string;
          Var: number | string;
          Min: number | string;
          'p5%': number | string;
          'p25%': number | string;
          'p50%': number | string;
          'p75%': number | string;
          'p95%': number | string;
          'p99%': number | string;
          Max: number | string;
        }>;
        rowsToShow: number; // Default 20
        writeup?: {
          content: string; // LLM-generated write-up
          lastGenerated: string | null;
        };
      };
    };
    modelValidation: {
      hasHoldDataset: boolean;
      bestModel: {
        modelName: string;
        metrics: {
          accuracy: number;
          precision: number;
          recall: number;
          f1Score: number;
          aucRoc: number;
          aucPr: number;
          logLoss: number;
        };
      };
      writeup?: string; // LLM-generated writeup
    };
    modelSelection: ModelSelectionSummary;
  };
  
  // Model Owner Section
  modelOwner: {
    approvedBy: string; // Editable field
    createdBy: string; // User name who generated documentation
    createdOn: string; // ISO timestamp when documentation was generated
  };
  
  // Model Performance Section
  modelPerformance: {
    features: {
      totalCount: number;
      usedFeatures: string[]; // List of all used features
      topFeatures: Array<{
        featureName: string;
        importance: number; // SHAP value with sign
        description: string; // From data dictionary or empty
      }>;
      topN: number; // Number of top features to display (default 20)
      categoryDistribution: Record<string, number>; // category name -> count of features
      categoryColors: Record<string, string>; // category name -> color for chart
    };
    rocCurves?: {
      train: Array<{
        modelName: string;
        modelId: string;
        rocData: {
          fpr: number[];
          tpr: number[];
          thresholds: number[];
          auc: number;
        };
        color: string;
      }>;
      test: Array<{
        modelName: string;
        modelId: string;
        rocData: {
          fpr: number[];
          tpr: number[];
          thresholds: number[];
          auc: number;
        };
        color: string;
      }>;
    };
    radarCharts?: {
      train: Array<{
        modelName: string;
        modelId: string;
        accuracy: number;
        precision: number;
        recall: number;
        f1Score: number;
        aucRoc: number;
        color: string;
      }>;
      test: Array<{
        modelName: string;
        modelId: string;
        accuracy: number;
        precision: number;
        recall: number;
        f1Score: number;
        aucRoc: number;
        color: string;
      }>;
    };
    confusionMatrices?: Array<{
      modelName: string;
      modelId: string;
      matrix: number[][]; // Test confusion matrix
      trainMatrix?: number[][]; // Optional train confusion matrix
      accuracy: number;
      trainAccuracy?: number;
      f1Score: number;
      trainF1Score?: number;
      color: string;
    }>;
    monotonicity?: Array<{
      modelName: string;
      modelId: string;
      monotonicityScore: number; // percentage (0-100)
      ksStatistic: number;
      ksThreshold: number;
      liftTopDecile: number | null;
      overallBadRate: number;
      auc: number;
      gini: number;
      violations: Array<{
        fromDecile: number;
        toDecile: number;
        drop: number;
      }>;
      deciles: Array<Record<string, any>>;
      decileProgressionWriteup?: string; // LLM-generated explanation
      psi?: {
        value: number;
        status: 'Stable' | 'Moderate' | 'Significant';
        interpretation: string;
      };
      csi?: Array<{
        variable: string;
        csiValue: number;
        status: 'Stable' | 'Moderate' | 'Significant';
      }>;
    }>;
    monotonicitySummary?: {
      writeup: string; // LLM-generated 2-3 line writeup
      lastGenerated: string | null;
    };
    granularAccuracy?: {
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
      variablesToShow: number; // Default 5
    };
    explainability?: {
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
          featureCount: number | 'all'; // Default based on UI
        };
        waterfall?: {
          data: Array<{
            feature: string;
            feature_value: number;
            shap_value: number;
          }>;
          baseValue: number;
          featureCount: number | 'all'; // Default based on UI
        };
      };
      pdp?: {
        data: Array<{
          feature_name: string;
          values: Array<{ x: number; y: number }>;
          ice_lines?: number[][];
        }>;
        featureCount: number | 'all'; // Default 5
        maxIceLines: number; // Default 100
      };
      writeup?: {
        content: string;
        lastGenerated: string;
      };
    };
  };
  
  // Data Insights Section (dynamic based on selected insight types)
  dataInsights: {
    bivariateAnalysis?: {
      insights: string[]; // Bullet point insights from LLM
      edaReport: Array<{
        Variable: string;
        'Event rate range': string;
        Insight: string;
      }>;
      rowsToShow: number | string; // Can be number (5, 20, 100), "all", or "used_features" - Default "used_features"
    };
    ivAnalysis?: {
      insights: string[]; // Bullet point insights from LLM
      edaReport: Array<{
        Variable: string;
        IV: number;
      }>;
      rowsToShow: number | string; // Can be number (5, 20, 100), "all", or "used_features" - Default "used_features"
    };
    correlationAnalysis?: {
      insights: string[]; // Bullet point insights from LLM
      edaReport: Array<Record<string, any>>; // Variable | var1 | var2 | ... (dynamic columns)
      rowsToShow: number | string; // Can be number (5, 20, 100), "all", or "used_features" - Default "used_features"
    };
    correlationAnalysisNumeric?: {  // NEW
      insights: string[]; // Bullet point insights from LLM
      edaReport: Array<{
        'Variable Name': string;
        'Type of Variable': string;
        'Pearson Coefficient': number;
        'Spearman Coefficient': number;
      }>;
      rowsToShow: number | string; // Can be number (5, 20, 100), "all", or "used_features" - Default "used_features"
    };
    vifAnalysis?: {  // NEW
      insights: string[]; // Bullet point insights from LLM
      edaReport: Array<{
        Variable: string;
        VIF: number;
        Interpretation: string;
      }>;
      rowsToShow: number | string; // Can be number (5, 20, 100), "all", or "used_features" - Default "used_features"
    };
    // vif?: {...};
    // correlationMatrix?: {...};
  };
  
  // Feature Engineering Section
  featureEngineering: {
    transformedVariables: Array<{
      new_variable_name: string;
      var_type: string;
      variable_definition: string;
      transformation_methods: string;
    }>;
    rowsToShow: number; // Default 20
    writeup?: {
      content: string; // LLM-generated write-up
      lastGenerated: string | null;
    };
  };
  
  // Future sections will be added here
  // modelTraining: {...};
  // modelEvaluation: {...};
  // explainability: {...};
  
  // Meta information
  meta: {
    lastUpdated: string;
    isGenerated: boolean;
  };
}

interface DocumentationContextType {
  documentationData: DocumentationData;
  updateObjectives: (objectives: Partial<DocumentationData['objectives']>) => void;
  updateModelObjective: (modelObjective: Partial<DocumentationData['objectives']['modelObjective']>) => void;
  updateDataSummary: (dataSummary: Partial<DocumentationData['objectives']['dataSummary']>) => void;
  updateModelDesign: (modelDesign: Partial<DocumentationData['modelDesign']>) => void;
  updateDataOverview: (dataOverview: Partial<DocumentationData['modelDesign']['dataOverview']>) => void;
  updateTargetDefinition: (targetDefinition: Partial<DocumentationData['modelDesign']['targetDefinition']>) => void;
  updateSamplingPlan: (samplingPlan: Partial<DocumentationData['modelDesign']['samplingPlan']>) => void;
  updateSegmentation: (segmentation: Partial<DocumentationData['modelDesign']['segmentation']>) => void;
  updateDataTreatment: (dataTreatment: Partial<DocumentationData['modelDesign']['dataTreatment']>) => void;
  updateModelValidation: (modelValidation: Partial<DocumentationData['modelDesign']['modelValidation']>) => void;
  updateModelSelection: (modelSelection: Partial<ModelSelectionSummary>) => void;
  updateModelOwner: (modelOwner: Partial<DocumentationData['modelOwner']>) => void;
  updateModelPerformance: (modelPerformance: Partial<DocumentationData['modelPerformance']>) => void;
  updateDataInsights: (dataInsights: Partial<DocumentationData['dataInsights']>) => void;
  updateFeatureEngineering: (featureEngineering: Partial<DocumentationData['featureEngineering']>) => void;
  generateDocumentation: () => void;
  resetDocumentation: () => void;
  isDocumentationGenerated: boolean;
}

const DocumentationContext = createContext<DocumentationContextType | undefined>(undefined);

export const useDocumentation = () => {
  const context = useContext(DocumentationContext);
  if (context === undefined) {
    throw new Error('useDocumentation must be used within a DocumentationProvider');
  }
  return context;
};

interface DocumentationProviderProps {
  children: ReactNode;
}

// Initial empty state
const initialDocumentationData: DocumentationData = {
  objectives: {
    modelObjective: {
      description: '',
      problemStatement: '',
      generatedObjective: '',
      lastGenerated: null,
    },
    dataSummary: {
      content: '',
      metadata: {
        columns: [],
        dataDictionary: null,
        lastGenerated: null,
      },
    },
  },
  modelDesign: {
    dataOverview: {
      datasetStats: {
        totalRows: 0,
        totalColumns: 0,
        numericalColumns: 0,
        categoricalColumns: 0,
        dateColumns: 0,
      },
      variableCategorization: {
        categories: {},
        colors: {},
        imageData: null,
      },
      dataQuality: {
        summary: '',
        metrics: {
          emptyColumns: 0,
          constantColumns: 0,
          sparseColumns: 0,
          formattingIssues: 0,
          emptyColumnNames: [],
          constantColumnNames: [],
          sparseColumnNames: [],
          formattingIssueColumnNames: [],
        },
        recommendations: [],
        lastGenerated: null,
      },
      edaReport: {
        table: [],
        rowsToShow: 20,
      },
    },
    targetDefinition: {
      targetVariableName: '',
      definition: '',
      eventRate: {
        eventCount: 0,
        totalCount: 0,
        percentage: 0,
      },
      lastGenerated: null,
    },
    samplingPlan: {
      hasSplit: false,
      train: {
        total: 0,
        eventCount: 0,
        eventRate: 0,
      },
      hold: {
        total: 0,
        eventCount: 0,
        eventRate: 0,
      },
      samplingIdentifier: '',
    },
    segmentation: {
      hasSegmentation: false,
      variablesUsed: undefined,
      method: undefined,
      segments: [],
      segmentSizesChart: undefined,
      segmentProportionsChart: undefined,
      ivVisualizationCharts: undefined,
      understanding: undefined,
    },
    dataTreatment: {
      qualityCheckPlan: {
        table: [],
        rowsToShow: 20,
      },
      implementedQualityChanges: {
        columnStats: [],
        rowsToShow: 20,
        writeup: undefined,
      },
    },
    modelValidation: {
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
    },
    modelSelection: getDefaultModelSelectionSummary(),
  },
  modelOwner: {
    approvedBy: '',
    createdBy: '',
    createdOn: '',
  },
  modelPerformance: {
    features: {
      totalCount: 0,
      usedFeatures: [],
      topFeatures: [],
      topN: 20, // Default to show top 20 features
      categoryDistribution: {},
      categoryColors: {},
    },
    rocCurves: undefined,
    radarCharts: undefined,
    confusionMatrices: undefined,
    monotonicity: undefined,
    monotonicitySummary: undefined,
    granularAccuracy: undefined,
    explainability: undefined,
  },
  dataInsights: {
    // Dynamic insight types will be populated based on user selection
  },
  featureEngineering: {
    transformedVariables: [],
    rowsToShow: 20,
    writeup: undefined,
  },
  meta: {
    lastUpdated: new Date().toISOString(),
    isGenerated: false,
  },
};

export const DocumentationProvider: React.FC<DocumentationProviderProps> = ({ children }) => {
  // Load from sessionStorage or use initial state
  // Note: If quota was exceeded in previous session, we won't have full data to restore
  // but that's okay - data stays in memory during the current session
  const [documentationData, setDocumentationData] = useState<DocumentationData>(() => {
    // Check if quota was exceeded in previous session
    const quotaExceeded = sessionStorage.getItem('model_documentation_quota_exceeded');
    if (quotaExceeded === 'true') {
      console.log('📦 Previous session had quota exceeded. Starting with initial state.');
      console.log('   Documentation will need to be regenerated, but current session data stays in memory.');
      // Clear the flag for this session
      try {
        sessionStorage.removeItem('model_documentation_quota_exceeded');
      } catch (e) {
        // Ignore errors when clearing
      }
      return initialDocumentationData;
    }
    
    // Try to load full data using optimized storage
    // Use async loading in useEffect since optimizedGetItem is async
    return initialDocumentationData;
  });

  // Load data from optimized storage on mount
  useEffect(() => {
    const loadStoredData = async () => {
      try {
        const stored = await optimizedGetItem('model_documentation_data');
        if (stored) {
          try {
            const parsed = JSON.parse(stored);
            setDocumentationData(parsed);
            console.log('✅ Loaded documentation data from optimized storage');
          } catch (e) {
            console.error('Failed to parse stored documentation data:', e);
          }
        }
      } catch (error) {
        console.error('Error loading documentation data:', error);
      }
    };
    
    loadStoredData();
  }, []);

  const [isDocumentationGenerated, setIsDocumentationGenerated] = useState(() => {
    const stored = sessionStorage.getItem('model_documentation_generated');
    return stored === 'true';
  });

  // Save to optimized storage whenever data changes
  // Uses compression and IndexedDB for large data
  useEffect(() => {
    const saveData = async () => {
      try {
        const serialized = JSON.stringify(documentationData);
        const result = await optimizedSetItem('model_documentation_data', serialized, 2);
        
        if (result.success) {
          if (result.usedIndexedDB) {
            console.log('✅ Stored documentation data in IndexedDB (compressed)');
          } else {
            console.log('✅ Stored documentation data in sessionStorage (compressed)');
          }
        } else {
          console.warn(`⚠️ Failed to store documentation data: ${result.error}`);
          // Fallback: Try to store a minimal flag
          try {
            sessionStorage.setItem('model_documentation_quota_exceeded', 'true');
            sessionStorage.setItem('model_documentation_last_updated', documentationData.meta.lastUpdated);
            console.warn('   Your documentation data remains in memory and will work normally during this session.');
            console.warn('   Note: Data may not persist after page refresh due to storage limits.');
          } catch (e) {
            console.warn('⚠️ Could not store quota exceeded flag, but data remains in memory.');
          }
        }
      } catch (error: any) {
        console.error('Error saving documentation to optimized storage:', error);
        // Fallback: Try to store a minimal flag
        try {
          sessionStorage.setItem('model_documentation_quota_exceeded', 'true');
          sessionStorage.setItem('model_documentation_last_updated', documentationData.meta.lastUpdated);
        } catch (e) {
          // Ignore errors
        }
      }
    };
    
    saveData();
  }, [documentationData]);

  useEffect(() => {
    try {
      sessionStorage.setItem('model_documentation_generated', isDocumentationGenerated.toString());
    } catch (error: any) {
      if (error.name === 'QuotaExceededError' || error.code === 22) {
        console.warn('⚠️ Could not save documentation generated flag due to quota exceeded.');
      } else {
        console.error('Error saving documentation generated flag:', error);
      }
    }
  }, [isDocumentationGenerated]);

  const updateObjectives = (objectives: Partial<DocumentationData['objectives']>) => {
    setDocumentationData(prev => ({
      ...prev,
      objectives: {
        ...prev.objectives,
        ...objectives,
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateModelObjective = (modelObjective: Partial<DocumentationData['objectives']['modelObjective']>) => {
    setDocumentationData(prev => ({
      ...prev,
      objectives: {
        ...prev.objectives,
        modelObjective: {
          ...prev.objectives.modelObjective,
          ...modelObjective,
        },
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateDataSummary = (dataSummary: Partial<DocumentationData['objectives']['dataSummary']>) => {
    setDocumentationData(prev => ({
      ...prev,
      objectives: {
        ...prev.objectives,
        dataSummary: {
          ...prev.objectives.dataSummary,
          ...dataSummary,
          metadata: {
            ...prev.objectives.dataSummary.metadata,
            ...(dataSummary.metadata || {}),
          },
        },
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateModelDesign = (modelDesign: Partial<DocumentationData['modelDesign']>) => {
    setDocumentationData(prev => ({
      ...prev,
      modelDesign: {
        ...prev.modelDesign,
        ...modelDesign,
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateDataOverview = (dataOverview: Partial<DocumentationData['modelDesign']['dataOverview']>) => {
    setDocumentationData(prev => ({
      ...prev,
      modelDesign: {
        ...prev.modelDesign,
        dataOverview: {
          ...prev.modelDesign.dataOverview,
          ...dataOverview,
          datasetStats: {
            ...prev.modelDesign.dataOverview.datasetStats,
            ...(dataOverview.datasetStats || {}),
          },
          variableCategorization: {
            ...prev.modelDesign.dataOverview.variableCategorization,
            ...(dataOverview.variableCategorization || {}),
          },
          dataQuality: {
            ...prev.modelDesign.dataOverview.dataQuality,
            ...((dataOverview.dataQuality || {}) as any),
            metrics: {
              ...prev.modelDesign.dataOverview.dataQuality.metrics,
              ...((dataOverview.dataQuality?.metrics || {}) as any),
            },
          },
          edaReport: {
            ...prev.modelDesign.dataOverview.edaReport,
            ...(dataOverview.edaReport || {}),
            table: dataOverview.edaReport?.table || prev.modelDesign.dataOverview.edaReport?.table || [],
            rowsToShow: dataOverview.edaReport?.rowsToShow ?? prev.modelDesign.dataOverview.edaReport?.rowsToShow ?? 20,
          },
        },
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateTargetDefinition = (targetDefinition: Partial<DocumentationData['modelDesign']['targetDefinition']>) => {
    setDocumentationData(prev => ({
      ...prev,
      modelDesign: {
        ...prev.modelDesign,
        targetDefinition: {
          ...prev.modelDesign.targetDefinition,
          ...targetDefinition,
          eventRate: {
            ...prev.modelDesign.targetDefinition.eventRate,
            ...(targetDefinition.eventRate || {}),
          },
        },
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateSamplingPlan = (samplingPlan: Partial<DocumentationData['modelDesign']['samplingPlan']>) => {
    setDocumentationData(prev => ({
      ...prev,
      modelDesign: {
        ...prev.modelDesign,
        samplingPlan: {
          ...prev.modelDesign.samplingPlan,
          ...samplingPlan,
          train: {
            ...prev.modelDesign.samplingPlan.train,
            ...(samplingPlan.train || {}),
          },
          hold: {
            ...prev.modelDesign.samplingPlan.hold,
            ...(samplingPlan.hold || {}),
          },
        },
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateSegmentation = (segmentation: Partial<DocumentationData['modelDesign']['segmentation']>) => {
    setDocumentationData(prev => ({
      ...prev,
      modelDesign: {
        ...prev.modelDesign,
        segmentation: {
          ...prev.modelDesign.segmentation,
          ...segmentation,
          segments: segmentation.segments || prev.modelDesign.segmentation.segments,
        },
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateDataTreatment = (dataTreatment: Partial<DocumentationData['modelDesign']['dataTreatment']>) => {
    setDocumentationData(prev => ({
      ...prev,
      modelDesign: {
        ...prev.modelDesign,
        dataTreatment: {
          ...prev.modelDesign.dataTreatment,
          ...dataTreatment,
          qualityCheckPlan: {
            ...prev.modelDesign.dataTreatment.qualityCheckPlan,
            ...(dataTreatment.qualityCheckPlan || {}),
          },
          implementedQualityChanges: {
            ...prev.modelDesign.dataTreatment.implementedQualityChanges,
            ...(dataTreatment.implementedQualityChanges || {}),
          },
        },
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateModelValidation = (modelValidation: Partial<DocumentationData['modelDesign']['modelValidation']>) => {
    setDocumentationData(prev => ({
      ...prev,
      modelDesign: {
        ...prev.modelDesign,
        modelValidation: {
          ...prev.modelDesign.modelValidation,
          ...modelValidation,
          bestModel: {
            ...prev.modelDesign.modelValidation.bestModel,
            ...(modelValidation.bestModel || {}),
            metrics: {
              ...prev.modelDesign.modelValidation.bestModel.metrics,
              ...(modelValidation.bestModel?.metrics || {}),
            },
          },
        },
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateModelSelection = (modelSelection: Partial<ModelSelectionSummary>) => {
    setDocumentationData(prev => ({
      ...prev,
      modelDesign: {
        ...prev.modelDesign,
        modelSelection: {
          ...prev.modelDesign.modelSelection,
          ...modelSelection,
          finalVariables: {
            ...prev.modelDesign.modelSelection.finalVariables,
            ...(modelSelection.finalVariables || {}),
          },
          hyperparameters: {
            ...prev.modelDesign.modelSelection.hyperparameters,
            ...(modelSelection.hyperparameters || {}),
          },
          metadata: {
            ...prev.modelDesign.modelSelection.metadata,
            ...(modelSelection.metadata || {}),
          },
        },
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateModelOwner = (modelOwner: Partial<DocumentationData['modelOwner']>) => {
    setDocumentationData(prev => ({
      ...prev,
      modelOwner: {
        ...prev.modelOwner,
        ...modelOwner,
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateModelPerformance = (modelPerformance: Partial<DocumentationData['modelPerformance']>) => {
    setDocumentationData(prev => ({
      ...prev,
      modelPerformance: {
        ...prev.modelPerformance,
        ...modelPerformance,
        features: {
          ...prev.modelPerformance.features,
          ...(modelPerformance.features || {}),
        },
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const updateDataInsights = (dataInsights: Partial<DocumentationData['dataInsights']>) => {
    setDocumentationData(prev => {
      const updated = {
        ...prev.dataInsights,
        ...dataInsights,
      };
      
      // Only merge bivariateAnalysis if it's provided
      if (dataInsights.bivariateAnalysis !== undefined) {
        updated.bivariateAnalysis = {
          ...prev.dataInsights.bivariateAnalysis,
          ...dataInsights.bivariateAnalysis,
        };
      }
      
      // Only merge ivAnalysis if it's provided
      if (dataInsights.ivAnalysis !== undefined) {
        updated.ivAnalysis = {
          ...prev.dataInsights.ivAnalysis,
          ...dataInsights.ivAnalysis,
        };
      }
      
      // Only merge correlationAnalysis if it's provided
      if (dataInsights.correlationAnalysis !== undefined) {
        updated.correlationAnalysis = {
          ...prev.dataInsights.correlationAnalysis,
          ...dataInsights.correlationAnalysis,
        };
      }
      
      // Only merge correlationAnalysisNumeric if it's provided - NEW
      if (dataInsights.correlationAnalysisNumeric !== undefined) {
        updated.correlationAnalysisNumeric = {
          ...prev.dataInsights.correlationAnalysisNumeric,
          ...dataInsights.correlationAnalysisNumeric,
        };
      }
      return {
        ...prev,
        dataInsights: updated,
        meta: {
          ...prev.meta,
          lastUpdated: new Date().toISOString(),
        },
      };
    });
  };

  const updateFeatureEngineering = (featureEngineering: Partial<DocumentationData['featureEngineering']>) => {
    setDocumentationData(prev => ({
      ...prev,
      featureEngineering: {
        ...prev.featureEngineering,
        ...featureEngineering,
      },
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
      },
    }));
  };

  const generateDocumentation = () => {
    setDocumentationData(prev => ({
      ...prev,
      meta: {
        ...prev.meta,
        lastUpdated: new Date().toISOString(),
        isGenerated: true,
      },
    }));
    setIsDocumentationGenerated(true);
  };

  const resetDocumentation = () => {
    setDocumentationData(initialDocumentationData);
    setIsDocumentationGenerated(false);
    sessionStorage.removeItem('model_documentation_data');
    sessionStorage.removeItem('model_documentation_generated');
  };

  const value: DocumentationContextType = {
    documentationData,
    updateObjectives,
    updateModelObjective,
    updateDataSummary,
    updateModelDesign,
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
    resetDocumentation,
    isDocumentationGenerated,
  };

  return <DocumentationContext.Provider value={value}>{children}</DocumentationContext.Provider>;
};

