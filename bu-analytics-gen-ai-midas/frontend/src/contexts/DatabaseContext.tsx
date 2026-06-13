import React, { createContext, useContext, useState, ReactNode } from 'react';
import { apiIntegrationService } from '../services/apiServices';

export interface DatabaseConnection {
  id: string;
  name: string;
  type: 'sql' | 'snowflake' | 'aws_s3' | 'azure_blob' | 'fred_api' | 'fmp_api' | 'moonshot_api' | 'moodys_api' | 'bloomberg_api' | 'plaid_api' | 'crs_api' | 'creditriskmonitor_api';
  status: 'connected' | 'disconnected' | 'connecting' | 'error';
  config: {
    host?: string;
    port?: number;
    database?: string;
    username?: string;
    password?: string;
    ssl?: boolean;
    // Snowflake specific
    account?: string;
    warehouse?: string;
    schema?: string;
    // AWS S3 specific
    accessKey?: string;
    secretKey?: string;
    region?: string;
    bucket?: string;
    // Azure Blob specific
    connectionString?: string;
    containerName?: string;
    // API specific
    apiKey?: string;
    apiSecret?: string;
    baseUrl?: string;
    environment?: 'sandbox' | 'production';
    clientId?: string;
    clientSecret?: string;
    accessToken?: string;
    refreshToken?: string;
  };
  lastConnected?: Date;
  createdAt: Date;
  tables?: string[];
  error?: string;
}

interface DatabaseContextType {
  connections: DatabaseConnection[];
  activeConnection: DatabaseConnection | null;
  addConnection: (connection: Omit<DatabaseConnection, 'id' | 'createdAt'>) => string;
  updateConnection: (id: string, updates: Partial<DatabaseConnection>) => void;
  removeConnection: (id: string) => void;
  setActiveConnection: (id: string) => void;
  testConnection: (connection: Omit<DatabaseConnection, 'id' | 'createdAt'>) => Promise<boolean>;
  fetchTables: (connectionId: string) => Promise<string[]>;
  queryData: (connectionId: string, query: string) => Promise<any[]>;
  getConnectionById: (id: string) => DatabaseConnection | undefined;
}

const DatabaseContext = createContext<DatabaseContextType | undefined>(undefined);

export const useDatabase = () => {
  const context = useContext(DatabaseContext);
  if (context === undefined) {
    throw new Error('useDatabase must be used within a DatabaseProvider');
  }
  return context;
};

interface DatabaseProviderProps {
  children: ReactNode;
}

export const DatabaseProvider: React.FC<DatabaseProviderProps> = ({ children }) => {
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [activeConnection, setActiveConnectionState] = useState<DatabaseConnection | null>(null);

  const addConnection = (connectionData: Omit<DatabaseConnection, 'id' | 'createdAt'>) => {
    const newConnection: DatabaseConnection = {
      ...connectionData,
      id: `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      createdAt: new Date(),
    };
    
    setConnections(prev => [...prev, newConnection]);
    return newConnection.id;
  };

  const updateConnection = (id: string, updates: Partial<DatabaseConnection>) => {
    setConnections(prev => 
      prev.map(conn => 
        conn.id === id ? { ...conn, ...updates } : conn
      )
    );
    
    // Update active connection if it's the one being updated
    if (activeConnection?.id === id) {
      setActiveConnectionState(prev => prev ? { ...prev, ...updates } : null);
    }
  };

  const removeConnection = (id: string) => {
    setConnections(prev => prev.filter(conn => conn.id !== id));
    
    // Clear active connection if it's the one being removed
    if (activeConnection?.id === id) {
      setActiveConnectionState(null);
    }
  };

  const setActiveConnection = (id: string) => {
    const connection = connections.find(conn => conn.id === id);
    if (connection) {
      setActiveConnectionState(connection);
    }
  };

  // API connection testing with real integration
  const testConnection = async (connection: Omit<DatabaseConnection, 'id' | 'createdAt'>): Promise<boolean> => {
    // For API connections, use real API integration service
    if (connection.type.includes('_api')) {
      try {
        const fullConnection = {
          ...connection,
          id: 'test',
          createdAt: new Date()
        };
        return await apiIntegrationService.testConnection(fullConnection);
      } catch (error) {
        console.error('API connection test failed:', error);
        return false;
      }
    }
    
    // For database connections, simulate testing
    return new Promise((resolve) => {
      setTimeout(() => {
        const success = Math.random() > 0.2;
        resolve(success);
      }, 2000);
    });
  };

  const fetchTables = async (connectionId: string): Promise<string[]> => {
    return new Promise((resolve) => {
      // Simulate fetching tables
      setTimeout(() => {
        const mockTables = [
          'customers',
          'transactions',
          'accounts',
          'products',
          'branches',
          'employees',
          'audit_logs'
        ];
        resolve(mockTables);
      }, 1500);
    });
  };

  const queryData = async (connectionId: string, query: string): Promise<any[]> => {
    return new Promise((resolve) => {
      // Simulate data query
      setTimeout(() => {
        const mockData = [
          { id: 1, customer_id: 'C001', amount: 1500.00, date: '2024-01-15', type: 'Transfer' },
          { id: 2, customer_id: 'C002', amount: 2300.50, date: '2024-01-15', type: 'Deposit' },
          { id: 3, customer_id: 'C003', amount: 750.25, date: '2024-01-14', type: 'Withdrawal' },
          { id: 4, customer_id: 'C004', amount: 1200.00, date: '2024-01-14', type: 'Transfer' },
          { id: 5, customer_id: 'C005', amount: 3400.75, date: '2024-01-13', type: 'Deposit' }
        ];
        resolve(mockData);
      }, 2000);
    });
  };

  const getConnectionById = (id: string) => {
    return connections.find(conn => conn.id === id);
  };

  const value: DatabaseContextType = {
    connections,
    activeConnection,
    addConnection,
    updateConnection,
    removeConnection,
    setActiveConnection,
    testConnection,
    fetchTables,
    queryData,
    getConnectionById,
  };

  return <DatabaseContext.Provider value={value}>{children}</DatabaseContext.Provider>;
}; 