import { io, Socket } from 'socket.io-client';

// Types for the credit risk backend
export interface ProcessingJob {
  id: string;
  type: 'data_collection' | 'preprocessing' | 'feature_engineering' | 'training' | 'validation';
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  datasetId: string;
  configuration: any;
  results?: any;
  error?: string;
  startedAt?: string;
  completedAt?: string;
  duration?: number;
  createdAt: string;
  updatedAt: string;
  createdBy: string;
}

export interface DataSource {
  id: string;
  name: string;
  type: 'database' | 'api' | 'file' | 'stream';
  category: 'banking' | 'credit_bureau' | 'economic' | 'market' | 'alternative';
  connectionConfig: any;
  schema?: Record<string, string>;
  updateFrequency: 'real_time' | 'daily' | 'weekly' | 'monthly' | 'quarterly';
  dataVolume: string;
  status: 'active' | 'inactive' | 'error';
  lastSync?: string;
  createdAt: string;
  updatedAt: string;
}

export interface DataQualityReport {
  overall: {
    score: number;
    grade: 'A' | 'B' | 'C' | 'D' | 'F';
    issues: string[];
  };
  creditMetrics: Array<{
    name: string;
    description: string;
    score: number;
    status: 'good' | 'warning' | 'error';
    details?: string;
  }>;
  complianceStatus: Array<{
    regulation: string;
    requirement: string;
    compliant: boolean;
    details?: string;
  }>;
  recommendations: {
    quality: string[];
    creditRisk: string[];
    compliance: string[];
  };
  generatedAt: string;
  datasetId: string;
}

export interface DataCollectionConfig {
  dataSources: Array<{
    sourceId: string;
    enabled: boolean;
    config?: any;
  }>;
  timeRange: {
    start: string;
    end: string;
  };
  filters?: any;
  sampleSize?: number;
  anonymize: boolean;
  excludePII: boolean;
  consentRequired: boolean;
}

export interface PreprocessingConfig {
  missingValues: 'drop' | 'impute_mean' | 'impute_median' | 'impute_mode' | 'forward_fill' | 'backward_fill';
  outliers: 'keep' | 'remove' | 'winsorize_95' | 'winsorize_99' | 'iqr_method';
  scaling: 'none' | 'standard' | 'minmax' | 'robust' | 'quantile';
  encoding: 'one_hot' | 'label' | 'target' | 'binary' | 'frequency';
  featureSelection?: {
    method: 'correlation' | 'mutual_info' | 'chi2' | 'f_test' | 'rfe';
    threshold?: number;
    maxFeatures?: number;
  };
}

export interface FeatureEngineeringConfig {
  traditional: boolean;
  behavioral: boolean;
  macroeconomic: boolean;
  alternative: boolean;
  customFeatures?: Array<{
    name: string;
    formula: string;
    description: string;
  }>;
  interactionFeatures?: Array<{
    features: string[];
    method: 'multiply' | 'divide' | 'ratio' | 'polynomial';
  }>;
}

class CreditRiskAPIService {
  private baseUrl: string;
  private socket: Socket | null = null;
  private eventListeners: Map<string, Function[]> = new Map();

  constructor() {
    this.baseUrl = process.env.NODE_ENV === 'development' 
      ? 'http://localhost:3001/api' 
      : '/api';
  }

  // Initialize WebSocket connection for real-time updates
  initializeWebSocket(): Socket {
    if (this.socket) {
      return this.socket;
    }

    const socketUrl = process.env.NODE_ENV === 'development' 
      ? 'http://localhost:3001' 
      : window.location.origin;

    this.socket = io(socketUrl, {
      transports: ['websocket', 'polling'],
      timeout: 20000,
      forceNew: true
    });

    this.socket.on('connect', () => {
      console.log('✅ Connected to Credit Risk Backend');
      this.socket?.emit('join_model_builder');
    });

    this.socket.on('disconnect', () => {
      console.log('❌ Disconnected from Credit Risk Backend');
    });

    this.socket.on('model_builder_event', (event) => {
      this.notifyListeners(event.type, event.payload);
    });

    this.socket.on('job_update', (event) => {
      this.notifyListeners('job_update', event.payload);
    });

    return this.socket;
  }

  // Event listener management
  addEventListener(eventType: string, callback: Function): void {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, []);
    }
    this.eventListeners.get(eventType)?.push(callback);
  }

  removeEventListener(eventType: string, callback: Function): void {
    const listeners = this.eventListeners.get(eventType);
    if (listeners) {
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  private notifyListeners(eventType: string, payload: any): void {
    const listeners = this.eventListeners.get(eventType);
    if (listeners) {
      listeners.forEach(callback => callback(payload));
    }
  }

  // Subscribe to job updates
  subscribeToJob(jobId: string): void {
    if (this.socket) {
      this.socket.emit('subscribe_job', jobId);
    }
  }

  unsubscribeFromJob(jobId: string): void {
    if (this.socket) {
      this.socket.emit('unsubscribe_job', jobId);
    }
  }

  // API methods
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const { buildMidasAuthHeaders } = await import('./authHeaders');
    const defaultHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
      ...buildMidasAuthHeaders(),
    };

    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers as Record<string, string>),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
      throw new Error(errorData.error?.message || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  // Get available data sources
  async getDataSources(): Promise<DataSource[]> {
    const response = await this.request<{ data: DataSource[] }>('/model-builder/data-sources');
    return response.data;
  }

  // Start data collection
  async startDataCollection(config: DataCollectionConfig): Promise<ProcessingJob> {
    const response = await this.request<{ data: ProcessingJob }>('/model-builder/data-collection', {
      method: 'POST',
      body: JSON.stringify(config)
    });
    return response.data;
  }

  // Get data quality report
  async getDataQualityReport(datasetId: string): Promise<DataQualityReport> {
    const response = await this.request<{ data: DataQualityReport }>(`/model-builder/data-quality-report/${datasetId}`);
    return response.data;
  }

  // Start data preprocessing
  async startPreprocessing(datasetId: string, config: PreprocessingConfig): Promise<ProcessingJob> {
    const response = await this.request<{ data: ProcessingJob }>('/model-builder/preprocessing/start', {
      method: 'POST',
      body: JSON.stringify({ datasetId, config })
    });
    return response.data;
  }

  // Start feature engineering
  async startFeatureEngineering(datasetId: string, config: FeatureEngineeringConfig): Promise<ProcessingJob> {
    const response = await this.request<{ data: ProcessingJob }>('/model-builder/features/generate', {
      method: 'POST',
      body: JSON.stringify({ datasetId, config })
    });
    return response.data;
  }

  // Get job status
  async getJobStatus(jobId: string): Promise<ProcessingJob> {
    const response = await this.request<{ data: ProcessingJob }>(`/model-builder/jobs/${jobId}`);
    return response.data;
  }

  // Cancel job
  async cancelJob(jobId: string): Promise<boolean> {
    const response = await this.request<{ data: { cancelled: boolean } }>(`/model-builder/jobs/${jobId}/cancel`, {
      method: 'POST'
    });
    return response.data.cancelled;
  }

  // Get AI recommendations
  async getRecommendations(datasetId: string): Promise<any> {
    const response = await this.request<{ data: any }>(`/model-builder/recommendations/${datasetId}`);
    return response.data;
  }

  // Get feature importance
  async getFeatureImportance(datasetId: string): Promise<any> {
    const response = await this.request<{ data: any }>(`/model-builder/features/importance/${datasetId}`);
    return response.data;
  }

  // Get compliance status
  async getComplianceStatus(datasetId: string): Promise<any> {
    const response = await this.request<{ data: any }>(`/model-builder/compliance/${datasetId}`);
    return response.data;
  }

  // Cleanup
  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.eventListeners.clear();
  }
}

// Export singleton instance
export const creditRiskAPI = new CreditRiskAPIService(); 