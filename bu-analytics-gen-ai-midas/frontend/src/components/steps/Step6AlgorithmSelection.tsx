import React from 'react';
import { Target } from 'lucide-react';

interface Step6AlgorithmSelectionProps {
  // Algorithm selection functionality states
  selectedAlgorithmSteps: string[];
  setSelectedAlgorithmSteps: (steps: string[]) => void;
  
  // Algorithm selection handlers
  onAutoAlgorithmSelection: () => Promise<void>;
  onStandardAlgorithmSelection: () => Promise<void>;
  onAlgorithmStepToggle: (step: string, checked: boolean) => void;
  
  // Chat component
  renderStepChat: (step: number) => React.ReactNode;
}

const Step6AlgorithmSelection: React.FC<Step6AlgorithmSelectionProps> = ({
  selectedAlgorithmSteps,
  setSelectedAlgorithmSteps,
  onAutoAlgorithmSelection,
  onStandardAlgorithmSelection,
  onAlgorithmStepToggle,
  renderStepChat
}) => {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Algorithm Selection</h3>
        
        {/* Auto Algorithm Selection Section */}
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-3">1. Auto Algorithm Selection</h4>
          <p className="text-sm text-gray-600 mb-4">Let our AI agent automatically select the best algorithm for your data and problem</p>
          <button
            onClick={onAutoAlgorithmSelection}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
          >
            <Target className="h-4 w-4" />
            <span>Run Auto Algorithm Selection</span>
          </button>
        </div>

        {/* Standard Algorithm Selection Steps Section */}
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-3">2. Standard Algorithm Selection Steps</h4>
          <p className="text-sm text-gray-600 mb-4">Select from standard algorithm types to evaluate</p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            {/* Linear Algorithms */}
            <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
              <h5 className="font-medium text-blue-900 mb-2">Linear Algorithms</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedAlgorithmSteps.includes('linear_regression')}
                    onChange={(e) => onAlgorithmStepToggle('linear_regression', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">Linear Regression</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedAlgorithmSteps.includes('logistic_regression')}
                    onChange={(e) => onAlgorithmStepToggle('logistic_regression', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">Logistic Regression</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedAlgorithmSteps.includes('ridge_lasso')}
                    onChange={(e) => onAlgorithmStepToggle('ridge_lasso', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">Ridge/Lasso Regression</span>
                </label>
              </div>
            </div>
            
            {/* Tree-Based Algorithms */}
            <div className="bg-green-50 rounded-lg p-4 border border-green-200">
              <h5 className="font-medium text-green-900 mb-2">Tree-Based Algorithms</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedAlgorithmSteps.includes('decision_tree')}
                    onChange={(e) => onAlgorithmStepToggle('decision_tree', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">Decision Tree</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedAlgorithmSteps.includes('random_forest')}
                    onChange={(e) => onAlgorithmStepToggle('random_forest', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">Random Forest</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedAlgorithmSteps.includes('xgboost')}
                    onChange={(e) => onAlgorithmStepToggle('xgboost', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">XGBoost</span>
                </label>
              </div>
            </div>
            
            {/* Advanced Algorithms */}
            <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
              <h5 className="font-medium text-purple-900 mb-2">Advanced Algorithms</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedAlgorithmSteps.includes('svm')}
                    onChange={(e) => onAlgorithmStepToggle('svm', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">Support Vector Machine</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedAlgorithmSteps.includes('neural_network')}
                    onChange={(e) => onAlgorithmStepToggle('neural_network', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">Neural Network</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedAlgorithmSteps.includes('ensemble')}
                    onChange={(e) => onAlgorithmStepToggle('ensemble', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">Ensemble Methods</span>
                </label>
              </div>
            </div>
          </div>
          
          <button
            onClick={onStandardAlgorithmSelection}
            disabled={selectedAlgorithmSteps.length === 0}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Run Selected Algorithm Selection Tasks
          </button>
        </div>
      </div>

      {/* Chat Component */}
      {renderStepChat(6)}
    </div>
  );
};

export default Step6AlgorithmSelection;
