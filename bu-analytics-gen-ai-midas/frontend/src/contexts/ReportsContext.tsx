import React, { createContext, useContext, useState, ReactNode } from 'react';

interface Report {
  id: number;
  name: string;
  createdAt: string;
}

interface ReportsContextType {
  reports: Report[];
  addReport: (name: string) => void;
  getReports: () => Report[];
}

const ReportsContext = createContext<ReportsContextType | undefined>(undefined);

export const useReports = () => {
  const context = useContext(ReportsContext);
  if (context === undefined) {
    throw new Error('useReports must be used within a ReportsProvider');
  }
  return context;
};

interface ReportsProviderProps {
  children: ReactNode;
}

export const ReportsProvider: React.FC<ReportsProviderProps> = ({ children }) => {
  const [reports, setReports] = useState<Report[]>([]);

  const addReport = (name: string) => {
    const newReport: Report = {
      id: Date.now(),
      name: name.trim(),
      createdAt: new Date().toLocaleDateString()
    };
    setReports(prev => [...prev, newReport]);
    console.log('New report created:', newReport);
  };

  const getReports = () => reports;

  const value = {
    reports,
    addReport,
    getReports
  };

  return (
    <ReportsContext.Provider value={value}>
      {children}
    </ReportsContext.Provider>
  );
}; 