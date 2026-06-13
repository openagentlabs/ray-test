import React from 'react';
import { Split } from 'lucide-react';

interface Step5DataSplittingProps {
  // Data splitting functionality states
  selectedSplitSteps: string[];
  setSelectedSplitSteps: (steps: string[]) => void;
  
  // Data splitting handlers
  onAutoDataSplitting: () => Promise<void>;
  onStandardDataSplitting: () => Promise<void>;
  onSplitStepToggle: (step: string, checked: boolean) => void;
  
  // Chat component
  renderStepChat: (step: number) => React.ReactNode;
}

const Step5DataSplitting: React.FC<Step5DataSplittingProps> = ({
  selectedSplitSteps,
  setSelectedSplitSteps,
  onAutoDataSplitting,
  onStandardDataSplitting,
  onSplitStepToggle,
  renderStepChat
}) => {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Data Splitting Strategy</h3>
        
        {/* Auto Data Splitting Section */}
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-3">1. Auto Data Splitting</h4>
          <p className="text-sm text-gray-600 mb-4">Let our AI agent automatically determine the optimal data splitting strategy for your model</p>
          <button
            onClick={onAutoDataSplitting}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
          >
            <Split className="h-4 w-4" />
            <span>Run Auto Data Splitting</span>
          </button>
        </div>

        {/* Standard Data Splitting Steps Section */}
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-3">2. Standard Data Splitting Steps</h4>
          <p className="text-sm text-gray-600 mb-4">Select from standard data splitting strategies to implement</p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            {/* Split Ratios */}
            <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
              <h5 className="font-medium text-blue-900 mb-2">Split Ratios</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedSplitSteps.includes('train_test')}
                    onChange={(e) => onSplitStepToggle('train_test', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">Train/Test split</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedSplitSteps.includes('train_val_test')}
                    onChange={(e) => onSplitStepToggle('train_val_test', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">Train/Val/Test split</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedSplitSteps.includes('cross_validation')}
                    onChange={(e) => onSplitStepToggle('cross_validation', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">Cross-validation</span>
                </label>
              </div>
            </div>
            
            {/* Stratification */}
            <div className="bg-green-50 rounded-lg p-4 border border-green-200">
              <h5 className="font-medium text-green-900 mb-2">Stratification</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedSplitSteps.includes('stratified')}
                    onChange={(e) => onSplitStepToggle('stratified', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">Stratified sampling</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedSplitSteps.includes('time_series')}
                    onChange={(e) => onSplitStepToggle('time_series', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">Time series split</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedSplitSteps.includes('group')}
                    onChange={(e) => onSplitStepToggle('group', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">Group-based split</span>
                </label>
              </div>
            </div>
            
            {/* Validation Methods */}
            <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
              <h5 className="font-medium text-purple-900 mb-2">Validation Methods</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedSplitSteps.includes('kfold')}
                    onChange={(e) => onSplitStepToggle('kfold', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">K-fold validation</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedSplitSteps.includes('leave_one_out')}
                    onChange={(e) => onSplitStepToggle('leave_one_out', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">Leave-one-out</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedSplitSteps.includes('bootstrap')}
                    onChange={(e) => onSplitStepToggle('bootstrap', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">Bootstrap sampling</span>
                </label>
              </div>
            </div>
          </div>
          
          <button
            onClick={onStandardDataSplitting}
            disabled={selectedSplitSteps.length === 0}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Run Selected Data Splitting Tasks
          </button>
        </div>
      </div>

      {/* Chat Component */}
      {renderStepChat(5)}
    </div>
  );
};

export default Step5DataSplitting;
