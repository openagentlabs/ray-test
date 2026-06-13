export interface ChartData {
  type: 'line' | 'bar' | 'pie' | 'area' | 'column' | 'scatter' | 'table';
  data: any[][];
  options: any;
  title: string;
}

export interface ChartConfig {
  type: string;
  data: any[][];
  options: any;
  elementId: string;
}

// Sample data generators for different chart types
export const generateSampleData = (type: string, query: string) => {
  const baseData = {
    line: [
      ['Month', 'Revenue', 'Transactions'],
      ['Jan', 42000, 1250],
      ['Feb', 38000, 1100],
      ['Mar', 45000, 1350],
      ['Apr', 52000, 1500],
      ['May', 48000, 1400],
      ['Jun', 53000, 1600]
    ],
    bar: [
      ['Region', 'Revenue'],
      ['North', 22000],
      ['South', 15000],
      ['East', 27000],
      ['West', 17000],
      ['Central', 19000]
    ],
    pie: [
      ['Segment', 'Customers'],
      ['Premium', 25],
      ['Standard', 65],
      ['Basic', 10]
    ],
    area: [
      ['Month', 'Low Risk', 'Medium Risk', 'High Risk'],
      ['Jan', 65, 25, 10],
      ['Feb', 68, 22, 10],
      ['Mar', 70, 20, 10],
      ['Apr', 72, 18, 10],
      ['May', 75, 15, 10],
      ['Jun', 78, 12, 10]
    ],
    column: [
      ['Category', 'Q1', 'Q2', 'Q3', 'Q4'],
      ['Transactions', 1200, 1350, 1400, 1600],
      ['Revenue', 42000, 48000, 52000, 53000],
      ['Customers', 850, 920, 980, 1050]
    ],
    scatter: [
      ['Age', 'Credit Score', 'Risk Level'],
      [25, 750, 'Low'],
      [30, 720, 'Low'],
      [35, 680, 'Medium'],
      [40, 650, 'Medium'],
      [45, 600, 'High'],
      [50, 580, 'High']
    ],
    table: [
      ['Customer ID', 'Name', 'Balance', 'Risk Score'],
      ['C001', 'John Doe', 25000, 720],
      ['C002', 'Jane Smith', 45000, 780],
      ['C003', 'Bob Johnson', 15000, 650],
      ['C004', 'Alice Brown', 35000, 750],
      ['C005', 'Charlie Wilson', 55000, 800]
    ]
  };

  // Determine chart type based on query keywords
  const queryLower = query.toLowerCase();
  
  if (queryLower.includes('trend') || queryLower.includes('time') || queryLower.includes('month')) {
    return {
      type: 'line',
      data: baseData.line,
      options: {
        title: 'Revenue and Transaction Trends',
        curveType: 'function',
        legend: { position: 'top' },
        hAxis: { title: 'Month' },
        vAxis: { title: 'Amount' }
      }
    };
  }
  
  if (queryLower.includes('region') || queryLower.includes('area') || queryLower.includes('location')) {
    return {
      type: 'bar',
      data: baseData.bar,
      options: {
        title: 'Regional Revenue Distribution',
        legend: { position: 'none' },
        hAxis: { title: 'Region' },
        vAxis: { title: 'Revenue ($)' }
      }
    };
  }
  
  if (queryLower.includes('segment') || queryLower.includes('customer') || queryLower.includes('group')) {
    return {
      type: 'pie',
      data: baseData.pie,
      options: {
        title: 'Customer Segmentation',
        pieHole: 0.4,
        legend: { position: 'bottom' }
      }
    };
  }
  
  if (queryLower.includes('risk') || queryLower.includes('safety')) {
    return {
      type: 'area',
      data: baseData.area,
      options: {
        title: 'Risk Distribution Over Time',
        legend: { position: 'top' },
        hAxis: { title: 'Month' },
        vAxis: { title: 'Percentage (%)' }
      }
    };
  }
  
  if (queryLower.includes('quarter') || queryLower.includes('comparison') || queryLower.includes('multiple')) {
    return {
      type: 'column',
      data: baseData.column,
      options: {
        title: 'Quarterly Performance Comparison',
        legend: { position: 'top' },
        hAxis: { title: 'Category' },
        vAxis: { title: 'Value' }
      }
    };
  }
  
  if (queryLower.includes('correlation') || queryLower.includes('relationship') || queryLower.includes('scatter')) {
    return {
      type: 'scatter',
      data: baseData.scatter,
      options: {
        title: 'Age vs Credit Score Correlation',
        legend: { position: 'none' },
        hAxis: { title: 'Age' },
        vAxis: { title: 'Credit Score' }
      }
    };
  }
  
  if (queryLower.includes('table') || queryLower.includes('list') || queryLower.includes('data')) {
    return {
      type: 'table',
      data: baseData.table,
      options: {
        title: 'Customer Data Table',
        showRowNumber: true,
        width: '100%',
        height: '100%'
      }
    };
  }
  
  // Default to line chart
  return {
    type: 'line',
    data: baseData.line,
    options: {
      title: 'Data Analysis',
      curveType: 'function',
      legend: { position: 'top' },
      hAxis: { title: 'Time' },
      vAxis: { title: 'Value' }
    }
  };
};

export const renderChart = (elementId: string, chartConfig: ChartConfig) => {
  const { type, data, options } = chartConfig;
  
  // Load Google Charts
  if (typeof window !== 'undefined' && (window as any).google && (window as any).google.visualization) {
    const chartClass = (window as any).google.visualization[type.charAt(0).toUpperCase() + type.slice(1) + 'Chart'];
    if (chartClass) {
      const element = document.getElementById(elementId);
      if (element) {
        const chart = new chartClass(element);
        chart.draw((window as any).google.visualization.arrayToDataTable(data), options);
        return chart;
      }
    }
  }
  
  // Fallback for when Google Charts is not loaded
  console.warn('Google Charts not loaded');
  return null;
};

export const createChartElement = (elementId: string, chartConfig: ChartConfig) => {
  // Create chart container
  const container = document.createElement('div');
  container.id = elementId;
  container.style.width = '100%';
  container.style.height = '300px';
  container.style.marginTop = '10px';
  
  return container;
};

// Load Google Charts library
export const loadGoogleCharts = (): Promise<void> => {
  return new Promise((resolve, reject) => {
    if (typeof window !== 'undefined' && (window as any).google && (window as any).google.visualization) {
      resolve();
      return;
    }
    
    const script = document.createElement('script');
    script.src = 'https://www.gstatic.com/charts/loader.js';
    script.onload = () => {
      if ((window as any).google && (window as any).google.charts) {
        (window as any).google.charts.load('current', { packages: ['corechart', 'table'] });
        (window as any).google.charts.setOnLoadCallback(() => {
          resolve();
        });
      } else {
        reject(new Error('Google Charts failed to load'));
      }
    };
    script.onerror = reject;
    document.head.appendChild(script);
  });
}; 