import React, { useState, useEffect } from 'react';
import modelEvaluationService from '../../services/modelEvaluationService';
import ModelEvaluationMEEA from '../../pages/ModelEvaluationMEEA';

interface Step5ModelEvaluationProps {
  // Model evaluation functionality states
  selectedSplitSteps: string[];
  setSelectedSplitSteps: (steps: string[]) => void;
  
  // Model evaluation handlers
  onAutoDataSplitting: () => Promise<void>;
  onStandardDataSplitting: () => Promise<void>;
  onSplitStepToggle: (step: string, checked: boolean) => void;
  
  // Chat component
  renderStepChat: (step: number) => React.ReactNode;
  
  // Dataset info for Data Split
  activeDatasetId?: string | null;
  datasetAnalysis?: {
    totalRows: number;
  } | null;
}

const Step5ModelEvaluation: React.FC<Step5ModelEvaluationProps> = ({
  renderStepChat,
  activeDatasetId,
  datasetAnalysis,
}) => {
  const [modelIds, setModelIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch models for the current dataset on mount
  useEffect(() => {
    const fetchModels = async () => {
      setLoading(true);
      try {
        if (!activeDatasetId) {
          // In the wizard, if there is no active dataset, we don't show any global models
          console.log('Step5: No active dataset, skipping global model listing');
          setModelIds([]);
        } else {
          const response = await modelEvaluationService.listModelsByDataset(activeDatasetId);
          
          const models = response.models || [];
          const modelsWithMeea = models.filter((model: any) => model.has_meea_data);
          const modelIds = modelsWithMeea.map((model: any) => model.id);
          
          console.log(`Step5: Found ${modelIds.length} models with MEEA data for dataset ${activeDatasetId}`);
          setModelIds(modelIds);
        }
      } catch (error) {
        console.error('Error fetching models for MEEA:', error);
        setModelIds([]);
      } finally {
        setLoading(false);
      }
    };
    
    fetchModels();
  }, [activeDatasetId]);

  return (
    <div className="space-y-6">
      {/* MEEA Dashboard - Always Visible (no blue header) */}
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl border border-slate-200 dark:border-gray-800 overflow-hidden">
        <div className="p-0 lg:p-4">
          <div className="rounded-2xl border border-slate-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-inner">
            {loading ? (
              <div className="flex flex-col items-center justify-center h-[400px] p-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
                <p className="text-gray-600 dark:text-gray-300">Loading models...</p>
              </div>
            ) : (
              <ModelEvaluationMEEA
                embedMode
                initialModelIds={modelIds}
                datasetId={activeDatasetId || undefined}
                defaultMode={modelIds.length > 0 ? 'standard' : 'segmentation'}
              />
            )}
          </div>
        </div>
      </div>

      {/* Chat Component */}
      {renderStepChat(5)}
    </div>
  );
};

export default Step5ModelEvaluation;
