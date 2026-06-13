export interface ParseResult {
  data: any[];
  columns: string[];
  records: number;
  errors?: string[];
}

export const parseCSV = (csvText: string): ParseResult => {
  const lines = csvText.trim().split('\n');
  
  if (lines.length === 0) {
    return { data: [], columns: [], records: 0, errors: ['Empty file'] };
  }

  // Parse header row
  const headers = parseCSVLine(lines[0]);
  const columns = headers.map(header => header.trim());
  
  // Parse data rows
  const data: any[] = [];
  const errors: string[] = [];
  
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue; // Skip empty lines
    
    try {
      const values = parseCSVLine(line);
      
      // Create row object
      const row: any = {};
      columns.forEach((column, index) => {
        let value = values[index] || '';
        
        // Try to parse numbers
        const numValue = parseFloat(value);
        if (!isNaN(numValue) && value !== '') {
          row[column] = numValue;
        } else {
          row[column] = value;
        }
      });
      
      data.push(row);
    } catch (error) {
      errors.push(`Error parsing line ${i + 1}: ${error}`);
    }
  }
  
  return {
    data,
    columns,
    records: data.length,
    errors: errors.length > 0 ? errors : undefined
  };
};

// Parse a single CSV line handling quoted values
const parseCSVLine = (line: string): string[] => {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;
  
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  
  result.push(current);
  return result;
};

export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export const generateDatasetDescription = (records: number, size: string): string => {
  return `${records.toLocaleString()} records • ${size}`;
}; 