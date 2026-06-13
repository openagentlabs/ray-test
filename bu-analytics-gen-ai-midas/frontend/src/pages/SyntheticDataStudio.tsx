import React, { useState, useEffect } from 'react';
import { 
  FlaskConical, 
  Play, 
  Pause, 
  Download, 
  Settings, 
  BarChart3, 
  Database, 
  Users, 
  CreditCard, 
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Clock,
  Sparkles,
  Eye,
  EyeOff,
  RefreshCw,
  Save,
  Trash2,
  Copy,
  Building,
  DatabaseZap
} from 'lucide-react';

interface SyntheticDataset {
  id: string;
  name: string;
  type: 'credit_card' | 'mortgage' | 'personal_loan' | 'business_loan' | 'transaction';
  records: number;
  status: 'generating' | 'completed' | 'failed' | 'paused';
  progress: number;
  createdAt: Date;
  description: string;
  features: string[];
  quality: {
    completeness: number;
    consistency: number;
    realism: number;
  };
}

interface GenerationConfig {
  datasetType: 'credit_card' | 'mortgage' | 'personal_loan' | 'business_loan' | 'transaction';
  recordCount: number;
  timeRange: {
    start: Date;
    end: Date;
  };
  features: {
    customer_demographics: boolean;
    transaction_history: boolean;
    credit_scores: boolean;
    payment_patterns: boolean;
    risk_indicators: boolean;
    behavioral_metrics: boolean;
  };
  realism: 'low' | 'medium' | 'high';
  privacy: 'basic' | 'enhanced' | 'enterprise';
}

const SyntheticDataStudio: React.FC = () => {
  const [datasets, setDatasets] = useState<SyntheticDataset[]>([]);
  const [activeDataset, setActiveDataset] = useState<SyntheticDataset | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [config, setConfig] = useState<GenerationConfig>({
    datasetType: 'credit_card',
    recordCount: 10000,
    timeRange: {
      start: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000), // 1 year ago
      end: new Date()
    },
    features: {
      customer_demographics: true,
      transaction_history: true,
      credit_scores: true,
      payment_patterns: true,
      risk_indicators: true,
      behavioral_metrics: true
    },
    realism: 'high',
    privacy: 'enhanced'
  });

  // Mock datasets for demonstration
  useEffect(() => {
    const mockDatasets: SyntheticDataset[] = [
      {
        id: '1',
        name: 'Credit Card Transactions Q4 2024',
        type: 'credit_card',
        records: 50000,
        status: 'completed',
        progress: 100,
        createdAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000),
        description: 'Synthetic credit card transaction data with realistic spending patterns',
        features: ['customer_id', 'transaction_amount', 'merchant_category', 'location', 'timestamp'],
        quality: { completeness: 98, consistency: 95, realism: 92 }
      },
      {
        id: '2',
        name: 'Mortgage Applications 2024',
        type: 'mortgage',
        records: 25000,
        status: 'completed',
        progress: 100,
        createdAt: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000),
        description: 'Synthetic mortgage application data with credit risk indicators',
        features: ['applicant_income', 'credit_score', 'down_payment', 'loan_amount', 'debt_ratio'],
        quality: { completeness: 96, consistency: 94, realism: 89 }
      },
      {
        id: '3',
        name: 'Personal Loan Portfolio',
        type: 'personal_loan',
        records: 15000,
        status: 'generating',
        progress: 65,
        createdAt: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000),
        description: 'Personal loan data with default prediction features',
        features: ['loan_amount', 'interest_rate', 'term_length', 'purpose', 'credit_history'],
        quality: { completeness: 0, consistency: 0, realism: 0 }
      }
    ];
    setDatasets(mockDatasets);
  }, []);

  const datasetTypes = [
    { value: 'credit_card', label: 'Credit Card Transactions', icon: CreditCard },
    { value: 'mortgage', label: 'Mortgage Applications', icon: Building },
    { value: 'personal_loan', label: 'Personal Loans', icon: Users },
    { value: 'business_loan', label: 'Business Loans', icon: TrendingUp },
    { value: 'transaction', label: 'General Transactions', icon: BarChart3 }
  ];

  const handleGenerateDataset = async () => {
    setIsGenerating(true);
    setShowConfig(false);
    
    const newDataset: SyntheticDataset = {
      id: Date.now().toString(),
      name: `${config.datasetType.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())} Dataset`,
      type: config.datasetType,
      records: config.recordCount,
      status: 'generating',
      progress: 0,
      createdAt: new Date(),
      description: `Synthetic ${config.datasetType} data with ${config.realism} realism`,
      features: [],
      quality: { completeness: 0, consistency: 0, realism: 0 }
    };

    setDatasets(prev => [newDataset, ...prev]);
    setActiveDataset(newDataset);

    // Simulate generation progress
    const interval = setInterval(() => {
      setDatasets(prev => prev.map(ds => 
        ds.id === newDataset.id 
          ? { ...ds, progress: Math.min(ds.progress + Math.random() * 15, 100) }
          : ds
      ));
    }, 500);

    // Complete generation after 5 seconds
    setTimeout(() => {
      clearInterval(interval);
      setDatasets(prev => prev.map(ds => 
        ds.id === newDataset.id 
          ? { 
              ...ds, 
              status: 'completed', 
              progress: 100,
              quality: { completeness: 95 + Math.random() * 5, consistency: 90 + Math.random() * 10, realism: 85 + Math.random() * 15 }
            }
          : ds
      ));
      setIsGenerating(false);
    }, 5000);
  };

  const handlePauseResume = (datasetId: string) => {
    setDatasets(prev => prev.map(ds => 
      ds.id === datasetId 
        ? { ...ds, status: ds.status === 'generating' ? 'paused' : 'generating' }
        : ds
    ));
  };

  const handleDeleteDataset = (datasetId: string) => {
    setDatasets(prev => prev.filter(ds => ds.id !== datasetId));
    if (activeDataset?.id === datasetId) {
      setActiveDataset(null);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'generating': return <RefreshCw className="h-4 w-4 animate-spin text-blue-500" />;
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed': return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'paused': return <Pause className="h-4 w-4 text-yellow-500" />;
      default: return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'generating': return 'text-blue-600 bg-blue-50';
      case 'completed': return 'text-green-600 bg-green-50';
      case 'failed': return 'text-red-600 bg-red-50';
      case 'paused': return 'text-yellow-600 bg-yellow-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  return (
    <div className="h-full overflow-y-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg">
            <DatabaseZap className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Synthetic Data Studio</h1>
            <p className="text-gray-600">Generate realistic synthetic datasets for testing and development</p>
          </div>
        </div>
        <button
          onClick={() => setShowConfig(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all duration-200"
        >
          <Sparkles className="h-4 w-4" />
          <span>Generate Dataset</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Dataset List */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Generated Datasets</h3>
            <div className="space-y-3">
              {datasets.map((dataset) => (
                <div
                  key={dataset.id}
                  className={`p-4 rounded-lg border cursor-pointer transition-all duration-200 ${
                    activeDataset?.id === dataset.id
                      ? 'border-purple-300 bg-purple-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => setActiveDataset(dataset)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h4 className="font-medium text-gray-900 truncate">{dataset.name}</h4>
                      <p className="text-sm text-gray-600 mt-1">{dataset.description}</p>
                      <div className="flex items-center space-x-4 mt-2">
                        <span className="text-xs text-gray-500">{dataset.records.toLocaleString()} records</span>
                        <span className={`text-xs px-2 py-1 rounded-full ${getStatusColor(dataset.status)}`}>
                          {dataset.status}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {getStatusIcon(dataset.status)}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteDataset(dataset.id);
                        }}
                        className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  
                  {dataset.status === 'generating' && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                        <span>Progress</span>
                        <span>{dataset.progress}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${dataset.progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Dataset Details */}
        <div className="lg:col-span-2">
          {activeDataset ? (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">{activeDataset.name}</h3>
                  <p className="text-gray-600 mt-1">{activeDataset.description}</p>
                </div>
                <div className="flex items-center space-x-2">
                  <button className="p-2 text-gray-400 hover:text-gray-600 transition-colors">
                    <Copy className="h-4 w-4" />
                  </button>
                  <button className="p-2 text-gray-400 hover:text-gray-600 transition-colors">
                    <Download className="h-4 w-4" />
                  </button>
                  <button className="p-2 text-gray-400 hover:text-gray-600 transition-colors">
                    <Eye className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Dataset Info */}
                <div>
                  <h4 className="font-medium text-gray-900 mb-3">Dataset Information</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Type:</span>
                      <span className="font-medium">{datasetTypes.find(dt => dt.value === activeDataset.type)?.label}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Records:</span>
                      <span className="font-medium">{activeDataset.records.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Created:</span>
                      <span className="font-medium">{activeDataset.createdAt.toLocaleDateString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Status:</span>
                      <span className={`font-medium ${getStatusColor(activeDataset.status)}`}>
                        {activeDataset.status}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Quality Metrics */}
                <div>
                  <h4 className="font-medium text-gray-900 mb-3">Quality Metrics</h4>
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-600">Completeness</span>
                        <span className="font-medium">{activeDataset.quality.completeness}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-green-500 h-2 rounded-full"
                          style={{ width: `${activeDataset.quality.completeness}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-600">Consistency</span>
                        <span className="font-medium">{activeDataset.quality.consistency}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-blue-500 h-2 rounded-full"
                          style={{ width: `${activeDataset.quality.consistency}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-600">Realism</span>
                        <span className="font-medium">{activeDataset.quality.realism}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-purple-500 h-2 rounded-full"
                          style={{ width: `${activeDataset.quality.realism}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Features */}
              <div className="mt-6">
                <h4 className="font-medium text-gray-900 mb-3">Generated Features</h4>
                <div className="flex flex-wrap gap-2">
                  {activeDataset.features.map((feature, index) => (
                    <span
                      key={index}
                      className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
                    >
                      {feature}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
                          <div className="text-center py-12">
              <DatabaseZap className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Dataset Selected</h3>
              <p className="text-gray-600">Select a dataset from the list to view details</p>
            </div>
            </div>
          )}
        </div>
      </div>

      {/* Configuration Modal */}
      {showConfig && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-semibold text-gray-900">Generate Synthetic Dataset</h3>
              <button
                onClick={() => setShowConfig(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </div>

            <div className="space-y-6">
              {/* Dataset Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">Dataset Type</label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {datasetTypes.map((type) => (
                    <button
                      key={type.value}
                      onClick={() => setConfig(prev => ({ ...prev, datasetType: type.value as any }))}
                      className={`p-4 rounded-lg border text-left transition-all duration-200 ${
                        config.datasetType === type.value
                          ? 'border-purple-500 bg-purple-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <type.icon className="h-5 w-5 text-gray-600 mb-2" />
                      <div className="font-medium text-gray-900">{type.label}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Record Count */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Number of Records: {config.recordCount.toLocaleString()}
                </label>
                <input
                  type="range"
                  min="1000"
                  max="100000"
                  step="1000"
                  value={config.recordCount}
                  onChange={(e) => setConfig(prev => ({ ...prev, recordCount: parseInt(e.target.value) }))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>1K</span>
                  <span>100K</span>
                </div>
              </div>

              {/* Features */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">Features to Include</label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.entries(config.features).map(([key, value]) => (
                    <label key={key} className="flex items-center space-x-3">
                      <input
                        type="checkbox"
                        checked={value}
                        onChange={(e) => setConfig(prev => ({
                          ...prev,
                          features: { ...prev.features, [key]: e.target.checked }
                        }))}
                        className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                      />
                      <span className="text-sm text-gray-700">
                        {key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Realism Level */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">Realism Level</label>
                <div className="flex space-x-3">
                  {['low', 'medium', 'high'].map((level) => (
                    <button
                      key={level}
                      onClick={() => setConfig(prev => ({ ...prev, realism: level as any }))}
                      className={`px-4 py-2 rounded-lg border transition-all duration-200 ${
                        config.realism === level
                          ? 'border-purple-500 bg-purple-50 text-purple-700'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      {level.charAt(0).toUpperCase() + level.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Privacy Level */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">Privacy Level</label>
                <div className="flex space-x-3">
                  {['basic', 'enhanced', 'enterprise'].map((level) => (
                    <button
                      key={level}
                      onClick={() => setConfig(prev => ({ ...prev, privacy: level as any }))}
                      className={`px-4 py-2 rounded-lg border transition-all duration-200 ${
                        config.privacy === level
                          ? 'border-purple-500 bg-purple-50 text-purple-700'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      {level.charAt(0).toUpperCase() + level.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowConfig(false)}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerateDataset}
                disabled={isGenerating}
                className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 disabled:opacity-50"
              >
                {isGenerating ? 'Generating...' : 'Generate Dataset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SyntheticDataStudio; 