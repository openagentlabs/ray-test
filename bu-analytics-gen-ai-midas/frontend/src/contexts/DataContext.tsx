import React, { createContext, useContext, useState, ReactNode } from 'react';

export interface Dataset {
  id: string;
  name: string;
  description: string;
  type: string;
  size: string;
  records: number;
  lastUpdated: string;
  status: 'active' | 'processing' | 'error';
  data: any[];
  columns: string[];
  uploadedAt: Date;
}

interface DataContextType {
  datasets: Dataset[];
  activeDataset: Dataset | null;
  addDataset: (dataset: Omit<Dataset, 'id' | 'uploadedAt'>) => string;
  removeDataset: (id: string) => void;
  setActiveDataset: (id: string) => void;
  getDatasetById: (id: string) => Dataset | undefined;
  clearAllDatasets: () => void;
}

const DataContext = createContext<DataContextType | undefined>(undefined);

export const useData = () => {
  const context = useContext(DataContext);
  if (context === undefined) {
    throw new Error('useData must be used within a DataProvider');
  }
  return context;
};

interface DataProviderProps {
  children: ReactNode;
}

export const DataProvider: React.FC<DataProviderProps> = ({ children }) => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [activeDataset, setActiveDatasetState] = useState<Dataset | null>(null);

  const addDataset = (datasetData: Omit<Dataset, 'id' | 'uploadedAt'>) => {
    const newDataset: Dataset = {
      ...datasetData,
      id: `dataset_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      uploadedAt: new Date(),
    };
    
    console.log('🔍 DataContext Add Dataset Debug:', {
      inputDataLength: datasetData.data.length,
      inputRecords: datasetData.records,
      newDatasetDataLength: newDataset.data.length,
      newDatasetRecords: newDataset.records,
      isDataArraySame: datasetData.data === newDataset.data
    });
    
    setDatasets(prev => [...prev, newDataset]);
    
    // Set as active if it's the first dataset
    if (datasets.length === 0) {
      setActiveDatasetState(newDataset);
      console.log('🔍 DataContext: Set as active dataset:', newDataset.name, 'with', newDataset.data.length, 'rows');
    }
    
    return newDataset.id;
  };

  const removeDataset = (id: string) => {
    setDatasets(prev => prev.filter(dataset => dataset.id !== id));
    
    // If removed dataset was active, set another as active or null
    if (activeDataset?.id === id) {
      const remainingDatasets = datasets.filter(dataset => dataset.id !== id);
      setActiveDatasetState(remainingDatasets.length > 0 ? remainingDatasets[0] : null);
    }
  };

  const setActiveDataset = (id: string) => {
    const dataset = datasets.find(d => d.id === id);
    if (dataset) {
      console.log('🔍 DataContext: Setting active dataset:', {
        id: dataset.id,
        name: dataset.name,
        records: dataset.records,
        dataLength: dataset.data.length,
        columnsLength: dataset.columns.length
      });
      setActiveDatasetState(dataset);
    } else {
      console.warn('🔍 DataContext: Dataset not found for id:', id);
    }
  };

  const getDatasetById = (id: string) => {
    return datasets.find(dataset => dataset.id === id);
  };

  const clearAllDatasets = () => {
    setDatasets([]);
    setActiveDatasetState(null);
  };

  const value: DataContextType = {
    datasets,
    activeDataset,
    addDataset,
    removeDataset,
    setActiveDataset,
    getDatasetById,
    clearAllDatasets,
  };

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}; 