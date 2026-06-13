import React from 'react';
import DataSplit from '../DataSplit';
import Step8AIExplainabilityAndDiagnostics from '../Step8AIExplainabilityAndDiagnostics';

interface Step8AIExplainabilityProps {
  // Chat component
  renderStepChat: (step: number) => React.ReactNode;
  
  // Dataset info for Data Split
  activeDatasetId?: string | null;
  datasetAnalysis?: {
    totalRows: number;
  } | null;
}

const Step8AIExplainability: React.FC<Step8AIExplainabilityProps> = ({
  renderStepChat,
  activeDatasetId,
  datasetAnalysis,
}) => {
  return (
    <div className="space-y-6">
      {/* Data Split Component */}
      <DataSplit activeDatasetId={activeDatasetId} datasetAnalysis={datasetAnalysis} stepKey={8} showSamplingUI={false} />

      {/* Step 8 - AI Explainability & Diagnostics: Explainability, Monotonicity, Granular Accuracy */}
      <Step8AIExplainabilityAndDiagnostics datasetId={activeDatasetId || undefined} />

      {/* Chat Component */}
      {renderStepChat(8)}
    </div>
  );
};

export default Step8AIExplainability;
