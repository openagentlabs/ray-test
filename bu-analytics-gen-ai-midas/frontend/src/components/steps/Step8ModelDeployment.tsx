import React from 'react';
import { Rocket } from 'lucide-react';

interface Step8ModelDeploymentProps {
  // Model deployment functionality states
  selectedDeploymentSteps: string[];
  setSelectedDeploymentSteps: (steps: string[]) => void;
  
  // Model deployment handlers
  onAutoModelDeployment: () => Promise<void>;
  onStandardModelDeployment: () => Promise<void>;
  onDeploymentStepToggle: (step: string, checked: boolean) => void;
  
  // Chat component
  renderStepChat: (step: number) => React.ReactNode;
}

const Step8ModelDeployment: React.FC<Step8ModelDeploymentProps> = ({
  selectedDeploymentSteps,
  setSelectedDeploymentSteps,
  onAutoModelDeployment,
  onStandardModelDeployment,
  onDeploymentStepToggle,
  renderStepChat
}) => {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Model Deployment</h3>
        
        {/* Auto Model Deployment Section */}
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-3">1. Auto Model Deployment</h4>
          <p className="text-sm text-gray-600 mb-4">Let our AI agent automatically deploy your trained model to production</p>
          <button
            onClick={onAutoModelDeployment}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
          >
            <Rocket className="h-4 w-4" />
            <span>Run Auto Model Deployment</span>
          </button>
        </div>

        {/* Standard Model Deployment Steps Section */}
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-3">2. Standard Model Deployment Steps</h4>
          <p className="text-sm text-gray-600 mb-4">Select from standard model deployment tasks to perform</p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            {/* Deployment Methods */}
            <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
              <h5 className="font-medium text-blue-900 mb-2">Deployment Methods</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedDeploymentSteps.includes('api_endpoint')}
                    onChange={(e) => onDeploymentStepToggle('api_endpoint', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">API endpoint</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedDeploymentSteps.includes('batch_processing')}
                    onChange={(e) => onDeploymentStepToggle('batch_processing', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">Batch processing</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-blue-600"
                    checked={selectedDeploymentSteps.includes('real_time')}
                    onChange={(e) => onDeploymentStepToggle('real_time', e.target.checked)}
                  />
                  <span className="text-sm text-blue-800">Real-time inference</span>
                </label>
              </div>
            </div>
            
            {/* Infrastructure */}
            <div className="bg-green-50 rounded-lg p-4 border border-green-200">
              <h5 className="font-medium text-green-900 mb-2">Infrastructure</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedDeploymentSteps.includes('containerization')}
                    onChange={(e) => onDeploymentStepToggle('containerization', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">Containerization</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedDeploymentSteps.includes('scaling')}
                    onChange={(e) => onDeploymentStepToggle('scaling', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">Auto-scaling</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-green-600"
                    checked={selectedDeploymentSteps.includes('monitoring')}
                    onChange={(e) => onDeploymentStepToggle('monitoring', e.target.checked)}
                  />
                  <span className="text-sm text-green-800">Monitoring setup</span>
                </label>
              </div>
            </div>
            
            {/* Model Management */}
            <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
              <h5 className="font-medium text-purple-900 mb-2">Model Management</h5>
              <div className="space-y-2">
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedDeploymentSteps.includes('versioning')}
                    onChange={(e) => onDeploymentStepToggle('versioning', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">Model versioning</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedDeploymentSteps.includes('a_b_testing')}
                    onChange={(e) => onDeploymentStepToggle('a_b_testing', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">A/B testing</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input 
                    type="checkbox" 
                    className="rounded text-purple-600"
                    checked={selectedDeploymentSteps.includes('rollback')}
                    onChange={(e) => onDeploymentStepToggle('rollback', e.target.checked)}
                  />
                  <span className="text-sm text-purple-800">Rollback strategy</span>
                </label>
              </div>
            </div>
          </div>
          
          <button
            onClick={onStandardModelDeployment}
            disabled={selectedDeploymentSteps.length === 0}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Run Selected Model Deployment Tasks
          </button>
        </div>
      </div>

      {/* Chat Component */}
      {renderStepChat(8)}
    </div>
  );
};

export default Step8ModelDeployment;
