import React from 'react';
import { TrendingUp } from 'lucide-react';

interface Step7ModelTrainingProps {
  // Model training functionality states
  selectedTrainingSteps: string[];
  setSelectedTrainingSteps: (steps: string[]) => void;
  
  // Model training handlers
  onAutoAlgorithmTraining: () => Promise<void>;
  onStandardAlgorithmTraining: () => Promise<void>;
  onTrainingStepToggle: (step: string, checked: boolean) => void;
  
  // Chat component
  renderStepChat: (step: number) => React.ReactNode;
}

const Step7ModelTraining: React.FC<Step7ModelTrainingProps> = ({
  selectedTrainingSteps,
  setSelectedTrainingSteps,
  onAutoAlgorithmTraining,
  onStandardAlgorithmTraining,
  onTrainingStepToggle,
  renderStepChat
}) => {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Algorithm Training</h3>
        
        {/* Auto Algorithm Training Section */}
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-3">1. Auto Algorithm Training</h4>
          <p className="text-sm text-gray-600 mb-4">Let our AI agent automatically train and optimize your selected algorithm</p>
          <button
            onClick={onAutoAlgorithmTraining}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
          >
            <TrendingUp className="h-4 w-4" />
            <span>Run Auto Algorithm Training</span>
          </button>
        </div>

        {/* Standard Algorithm Training Steps Section */}
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-3">2. Standard Algorithm Training Steps</h4>
          <p className="text-sm text-gray-600 mb-4">Select from standard algorithm training tasks to perform</p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            {/* Training Methods */}
            <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
              <h5 className="font-medium text-blue-900 mb-2">Training Methods</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedTrainingSteps.includes('hyperparameter_tuning')}
                    onChange={(e) => onTrainingStepToggle('hyperparameter_tuning', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">Hyperparameter tuning</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedTrainingSteps.includes('cross_validation')}
                    onChange={(e) => onTrainingStepToggle('cross_validation', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">Cross-validation</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedTrainingSteps.includes('early_stopping')}
                    onChange={(e) => onTrainingStepToggle('early_stopping', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">Early stopping</span>
                </label>
              </div>
            </div>
            
            {/* Optimization Techniques */}
            <div className="bg-green-50 rounded-lg p-4 border border-green-200">
              <h5 className="font-medium text-green-900 mb-2">Optimization Techniques</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedTrainingSteps.includes('grid_search')}
                    onChange={(e) => onTrainingStepToggle('grid_search', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">Grid search</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedTrainingSteps.includes('random_search')}
                    onChange={(e) => onTrainingStepToggle('random_search', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">Random search</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedTrainingSteps.includes('bayesian_optimization')}
                    onChange={(e) => onTrainingStepToggle('bayesian_optimization', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">Bayesian optimization</span>
                </label>
              </div>
            </div>
            
            {/* Algorithm Evaluation */}
            <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
              <h5 className="font-medium text-purple-900 mb-2">Algorithm Evaluation</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedTrainingSteps.includes('performance_metrics')}
                    onChange={(e) => onTrainingStepToggle('performance_metrics', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">Performance metrics</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedTrainingSteps.includes('algorithm_comparison')}
                    onChange={(e) => onTrainingStepToggle('algorithm_comparison', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">Algorithm comparison</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedTrainingSteps.includes('feature_importance')}
                    onChange={(e) => onTrainingStepToggle('feature_importance', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">Feature importance</span>
                </label>
              </div>
            </div>
          </div>
          
          <button
            onClick={onStandardAlgorithmTraining}
            disabled={selectedTrainingSteps.length === 0}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Run Selected Algorithm Training Tasks
          </button>
        </div>
      </div>

      {/* Chat Component */}
      {renderStepChat(7)}
    </div>
  );
};

export default Step7ModelTraining;
