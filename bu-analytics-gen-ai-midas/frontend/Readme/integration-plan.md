# Integration Plan: Backend Agent + Model Builder Step 2

## 🎯 **Current State vs Target State**

### **Current State (Step 2)**
- Static mock data for numerical/categorical variables
- Hardcoded data quality metrics
- Client-side transformations only
- No real data processing capabilities

### **Target State (Step 2 + Backend Agent)**
- Real-time data collection from multiple credit data sources
- Dynamic data quality assessment with live metrics
- Server-side data preprocessing and feature engineering
- Interactive data transformation with preview capabilities
- Credit risk-specific recommendations

---

## 🔄 **Step-by-Step Integration**

### **1. Backend API Integration**

#### **Update ModelBuilder.tsx Step 2 to use real APIs:**

```typescript
// Add to ModelBuilder.tsx
const [dataCollectionJob, setDataCollectionJob] = useState<ProcessingJob | null>(null);
const [dataQualityReport, setDataQualityReport] = useState<DataQualityReport | null>(null);
const [availableDataSources, setAvailableDataSources] = useState<DataSource[]>([]);

// Replace static data with API calls
useEffect(() => {
  if (currentStep === 2) {
    loadAvailableDataSources();
    loadDataQualityReport();
  }
}, [currentStep]);

const loadAvailableDataSources = async () => {
  try {
    const response = await fetch('/api/model-builder/data-sources');
    const sources = await response.json();
    setAvailableDataSources(sources);
  } catch (error) {
    console.error('Failed to load data sources:', error);
  }
};

const startDataCollection = async (config: DataCollectionConfig) => {
  try {
    const response = await fetch('/api/model-builder/data-collection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });
    const job = await response.json();
    setDataCollectionJob(job);
    
    // Start polling for job status
    pollJobStatus(job.id);
  } catch (error) {
    console.error('Failed to start data collection:', error);
  }
};
```

### **2. Real-time Progress Updates**

#### **WebSocket Integration:**

```typescript
// Add WebSocket connection for real-time updates
useEffect(() => {
  const socket = new WebSocket('ws://localhost:3001/model-builder');
  
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch (data.type) {
      case 'data_collection_progress':
        setDataCollectionJob(prev => ({
          ...prev,
          progress: data.progress
        }));
        break;
        
      case 'data_collection_completed':
        setDataCollectionJob(prev => ({
          ...prev,
          status: 'completed',
          results: data.results
        }));
        loadDataQualityReport();
        break;
    }
  };
  
  return () => socket.close();
}, []);
```

### **3. Enhanced Step 2 UI**

#### **Replace static content with dynamic components:**

```typescript
// Replace case 2 in renderStepContent()
case 2:
  return (
    <div className="space-y-6">
      {/* Data Source Selection */}
      <DataSourceSelector 
        sources={availableDataSources}
        onSelectionChange={handleDataSourceChange}
      />
      
      {/* Data Collection Configuration */}
      <DataCollectionConfig 
        onStart={startDataCollection}
        isLoading={dataCollectionJob?.status === 'running'}
      />
      
      {/* Real-time Progress */}
      {dataCollectionJob && (
        <DataCollectionProgress 
          job={dataCollectionJob}
          onCancel={cancelDataCollection}
        />
      )}
      
      {/* Live Data Quality Assessment */}
      {dataQualityReport && (
        <DataQualityDashboard 
          report={dataQualityReport}
          onRefresh={loadDataQualityReport}
        />
      )}
      
      {/* Interactive Data Preprocessing */}
      <DataPreprocessingPanel 
        dataset={dataCollectionJob?.results?.dataset}
        onPreprocess={startPreprocessing}
      />
    </div>
  );
```

---

## 🎯 **Credit Risk Specific Components**

### **1. DataSourceSelector Component**

```typescript
interface DataSourceSelectorProps {
  sources: DataSource[];
  onSelectionChange: (selected: DataSource[]) => void;
}

const DataSourceSelector: React.FC<DataSourceSelectorProps> = ({ sources, onSelectionChange }) => {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Credit Data Sources</h3>
      
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Core Banking Data */}
        <div className="p-4 border border-blue-200 rounded-lg bg-blue-50">
          <h4 className="font-medium text-blue-900 mb-2">🏦 Banking Data</h4>
          <div className="space-y-2">
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="text-blue-600" />
              <span className="text-sm">Transaction History</span>
            </label>
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="text-blue-600" />
              <span className="text-sm">Account Information</span>
            </label>
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="text-blue-600" />
              <span className="text-sm">Customer Demographics</span>
            </label>
          </div>
        </div>
        
        {/* Economic Data */}
        <div className="p-4 border border-green-200 rounded-lg bg-green-50">
          <h4 className="font-medium text-green-900 mb-2">📊 Economic Data</h4>
          <div className="space-y-2">
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="text-green-600" />
              <span className="text-sm">Unemployment Rate</span>
            </label>
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="text-green-600" />
              <span className="text-sm">GDP Growth</span>
            </label>
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="text-green-600" />
              <span className="text-sm">Interest Rates</span>
            </label>
          </div>
        </div>
        
        {/* Credit Bureau Data */}
        <div className="p-4 border border-purple-200 rounded-lg bg-purple-50">
          <h4 className="font-medium text-purple-900 mb-2">🔍 Credit Bureau</h4>
          <div className="space-y-2">
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="text-purple-600" />
              <span className="text-sm">Credit Scores</span>
            </label>
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="text-purple-600" />
              <span className="text-sm">Payment History</span>
            </label>
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="text-purple-600" />
              <span className="text-sm">Credit Utilization</span>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
};
```

### **2. DataCollectionProgress Component**

```typescript
const DataCollectionProgress: React.FC<{ job: ProcessingJob }> = ({ job }) => {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Data Collection Progress</h3>
      
      <div className="space-y-4">
        {/* Overall Progress */}
        <div>
          <div className="flex justify-between text-sm text-gray-600 mb-2">
            <span>Overall Progress</span>
            <span>{job.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div 
              className="bg-blue-600 h-3 rounded-full transition-all duration-300"
              style={{ width: `${job.progress}%` }}
            ></div>
          </div>
        </div>
        
        {/* Step-by-step Progress */}
        <div className="grid md:grid-cols-3 gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
              <CheckCircle className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900">Data Sources Connected</p>
              <p className="text-xs text-gray-500">3/3 sources active</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center animate-spin">
              <RefreshCw className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900">Collecting Data</p>
              <p className="text-xs text-gray-500">1.2M records processed</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center">
              <Circle className="h-5 w-5 text-gray-500" />
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Quality Assessment</p>
              <p className="text-xs text-gray-400">Pending</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
```

### **3. DataQualityDashboard Component**

```typescript
const DataQualityDashboard: React.FC<{ report: DataQualityReport }> = ({ report }) => {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-6">Credit Data Quality Assessment</h3>
      
      <div className="grid lg:grid-cols-2 gap-8">
        {/* Credit Risk Specific Metrics */}
        <div>
          <h4 className="font-medium text-gray-900 mb-4">Credit Risk Data Quality</h4>
          <div className="space-y-3">
            {report.creditMetrics.map((metric, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <span className="text-sm font-medium text-gray-900">{metric.name}</span>
                  <p className="text-xs text-gray-600">{metric.description}</p>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium">{metric.score}%</span>
                  <div className={`w-3 h-3 rounded-full ${
                    metric.score >= 90 ? 'bg-green-500' :
                    metric.score >= 70 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}></div>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Compliance Status */}
        <div>
          <h4 className="font-medium text-gray-900 mb-4">Regulatory Compliance</h4>
          <div className="space-y-3">
            {report.complianceStatus.map((status, i) => (
              <div key={i} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
                <div>
                  <span className="text-sm font-medium text-gray-900">{status.regulation}</span>
                  <p className="text-xs text-gray-600">{status.requirement}</p>
                </div>
                <div className={`px-2 py-1 rounded text-xs font-medium ${
                  status.compliant 
                    ? 'bg-green-100 text-green-700' 
                    : 'bg-red-100 text-red-700'
                }`}>
                  {status.compliant ? 'Compliant' : 'Non-Compliant'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* AI-Powered Recommendations */}
      <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
        <h4 className="font-medium text-blue-900 mb-3">🤖 AI Recommendations</h4>
        <div className="grid md:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="font-medium text-blue-800">Data Quality Improvements:</p>
            <ul className="text-blue-700 mt-1 space-y-1">
              {report.recommendations.quality.map((rec, i) => (
                <li key={i}>• {rec}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="font-medium text-blue-800">Credit Risk Enhancements:</p>
            <ul className="text-blue-700 mt-1 space-y-1">
              {report.recommendations.creditRisk.map((rec, i) => (
                <li key={i}>• {rec}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
```

---

## 🚀 **Implementation Timeline**

### **Week 1: Backend Foundation**
1. Set up Express.js + TypeScript backend
2. Configure PostgreSQL + Redis
3. Create basic API structure
4. Implement authentication middleware

### **Week 2: Core Agent Development**
1. Build CreditRiskDataAgent class
2. Implement DataCollectionOrchestrator
3. Create data source integrators (FRED, FMP)
4. Set up WebSocket server for real-time updates

### **Week 3: Frontend Integration**
1. Update ModelBuilder.tsx Step 2
2. Create new React components (DataSourceSelector, etc.)
3. Implement WebSocket client
4. Add error handling and loading states

### **Week 4: Advanced Features**
1. Add credit-specific data quality metrics
2. Implement compliance validation
3. Create AI-powered recommendations
4. Add data preprocessing capabilities

---

## 🔧 **Configuration & Testing**

### **Environment Variables**
```bash
# Backend
PORT=3001
DATABASE_URL=postgresql://username:password@localhost:5432/credit_risk_db
REDIS_URL=redis://localhost:6379
JWT_SECRET=your_jwt_secret

# External APIs
FRED_API_KEY=your_fred_api_key
FMP_API_KEY=your_fmp_api_key
MOONSHOT_API_KEY=your_moonshot_api_key

# ML Engine
ML_ENGINE_URL=http://localhost:8000
```

### **Testing Strategy**
```typescript
// Integration tests for Step 2
describe('ModelBuilder Step 2 Integration', () => {
  test('should load available data sources', async () => {
    // Test API integration
  });
  
  test('should start data collection job', async () => {
    // Test job creation and WebSocket updates
  });
  
  test('should display real-time progress', async () => {
    // Test WebSocket message handling
  });
  
  test('should show data quality assessment', async () => {
    // Test quality metrics display
  });
});
```

This integration plan transforms your static Model Builder Step 2 into a dynamic, real-time credit risk data processing system with enterprise-grade capabilities. 