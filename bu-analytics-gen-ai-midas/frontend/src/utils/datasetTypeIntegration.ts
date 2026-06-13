/**
 * Dataset Type Classification Integration Utility
 * 
 * This utility provides helper functions to integrate dataset type classification
 * into the upload flow. Import and use these functions in your upload handlers.
 */

import { fastApiService, DatasetTypeClassificationResponse } from '../services/fastApiService';

export interface DatasetConfig {
  target_variable: string;
  target_variable_type: 'Numerical' | 'Categorical';
  dataset_structure_type: 'classification' | 'regression' | 'time_series' | 'others';
  problem_statement: string;
  data_dictionary: string;
  unique_id_combinations?: string[];
  segmentation_variable?: string;
  sample_identifier_variable?: string;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

/**
 * Classify dataset type and update configuration.
 * @param dataset_id Backend dataset id after upload (required for by-id classification).
 */
export async function classifyAndUpdateDatasetConfig(
  dataset_id: string,
  file: File,
  currentConfig: DatasetConfig | null,
  setDatasetConfig: (config: DatasetConfig) => void,
  setChatMessages?: (updater: (prev: Record<number, ChatMessage[]>) => Record<number, ChatMessage[]>) => void,
  showNotification?: (message: string, type: 'success' | 'error') => void
): Promise<DatasetTypeClassificationResponse | null> {
  try {
    console.log('🤖 Starting dataset type classification for file:', file.name);
    
    const classificationResponse = await fastApiService.classifyDatasetTypeById({
      dataset_id,
      target_variable: currentConfig?.target_variable || '',
      target_variable_type: currentConfig?.target_variable_type || 'Categorical',
    });
    
    if (classificationResponse.success) {
      console.log('✅ Dataset classification completed:', {
        type: classificationResponse.dataset_type,
        confidence: classificationResponse.confidence
      });
      
      // Update the dataset configuration
      const updatedConfig: DatasetConfig = {
        target_variable: currentConfig?.target_variable || '',
        target_variable_type: currentConfig?.target_variable_type || 'Categorical',
        dataset_structure_type: classificationResponse.dataset_type,
        problem_statement: currentConfig?.problem_statement || '',
        data_dictionary: currentConfig?.data_dictionary || '',
        unique_id_combinations: currentConfig?.unique_id_combinations || [],
        segmentation_variable: currentConfig?.segmentation_variable || '',
        sample_identifier_variable: currentConfig?.sample_identifier_variable || ''
      };
      
      // Update state
      setDatasetConfig(updatedConfig);
      
      // Persist to session storage
      sessionStorage.setItem('dataset_config', JSON.stringify(updatedConfig));
      
      // Show success notification
      if (showNotification) {
        const confidencePercent = (classificationResponse.confidence * 100).toFixed(1);
        showNotification(
          `Dataset classified as ${classificationResponse.dataset_type.replace('_', ' ')} (${confidencePercent}% confidence)`,
          'success'
        );
      }
      
      // Add AI assistant message to chat (optional)
      if (setChatMessages) {
        const aiMessage: ChatMessage = {
          id: `ai-classification-${Date.now()}`,
          type: 'assistant',
          content: createClassificationMessage(classificationResponse),
          timestamp: new Date()
        };
        
        setChatMessages(prev => ({
          ...prev,
          [1]: [...(prev[1] || []), aiMessage] // Add to step 1 chat
        }));
      }
      
      return classificationResponse;
      
    } else {
      throw new Error(classificationResponse.message || 'Classification failed');
    }
    
  } catch (error) {
    console.error('❌ Dataset type classification failed:', error);
    
    // Show error notification
    if (showNotification) {
      showNotification('Dataset classification failed, using default type', 'error');
    }
    
    // Don't block the upload flow - just use default 'others' type
    if (currentConfig) {
      const configWithDefault: DatasetConfig = {
        ...currentConfig,
        dataset_structure_type: 'others'
      };
      setDatasetConfig(configWithDefault);
      sessionStorage.setItem('dataset_config', JSON.stringify(configWithDefault));
    }
    
    return null;
  }
}

/**
 * Create a formatted chat message for the classification result
 */
function createClassificationMessage(response: DatasetTypeClassificationResponse): string {
  const typeDisplay = response.dataset_type.replace('_', ' ').toUpperCase();
  const confidencePercent = (response.confidence * 100).toFixed(1);
  
  let message = `🤖 **Dataset Analysis Complete**\n\n`;
  message += `**Type:** ${typeDisplay}\n`;
  message += `**Confidence:** ${confidencePercent}%\n\n`;
  message += `**Reasoning:** ${response.reasoning}\n\n`;
  
  if (response.recommendations && response.recommendations.length > 0) {
    message += `**Recommendations:**\n`;
    message += response.recommendations.map(rec => `• ${rec}`).join('\n');
  }
  
  return message;
}

/**
 * Check if dataset type classification should run
 * (e.g., only run once per file, or if confidence is low)
 */
export function shouldRunClassification(
  fileName: string,
  currentConfig: DatasetConfig | null
): boolean {
  // Don't run if we already have a classification for this file
  const lastClassifiedFile = sessionStorage.getItem('last_classified_file');
  if (lastClassifiedFile === fileName && currentConfig?.dataset_structure_type) {
    console.log('🔄 Skipping classification - already classified this file');
    return false;
  }
  
  return true;
}

/**
 * Mark file as classified to avoid re-running
 */
export function markFileAsClassified(fileName: string): void {
  sessionStorage.setItem('last_classified_file', fileName);
}

/**
 * Integration example for file classification before upload
 */
export async function handleFileClassificationBeforeUpload(
  dataset_id: string,
  file: File,
  currentConfig: DatasetConfig | null,
  setDatasetConfig: (config: DatasetConfig) => void,
  setChatMessages?: (updater: (prev: Record<number, ChatMessage[]>) => Record<number, ChatMessage[]>) => void,
  showNotification?: (message: string, type: 'success' | 'error') => void
): Promise<DatasetTypeClassificationResponse | null> {
  // Run classification if needed
  if (shouldRunClassification(file.name, currentConfig)) {
    const classificationResult = await classifyAndUpdateDatasetConfig(
      dataset_id,
      file,
      currentConfig,
      setDatasetConfig,
      setChatMessages,
      showNotification
    );
    
    if (classificationResult) {
      markFileAsClassified(file.name);
    }
    
    return classificationResult;
  }
  
  return null;
}

/**
 * Get display name for dataset type
 */
export function getDatasetTypeDisplayName(type: string): string {
  const displayNames: Record<string, string> = {
    'classification': 'Classification',
    'regression': 'Regression',
    'time_series': 'Time Series',
    'others': 'Others'
  };
  
  return displayNames[type] || type;
}

/**
 * Get description for dataset type
 */
export function getDatasetTypeDescription(type: string): string {
  const descriptions: Record<string, string> = {
    'classification': 'Machine learning problem for predicting discrete categories or classes',
    'regression': 'Machine learning problem for predicting continuous numerical values',
    'time_series': 'Dataset with temporal components requiring time series analysis or forecasting',
    'others': 'Datasets for clustering, anomaly detection, or other specialized ML tasks'
  };
  
  return descriptions[type] || 'Unknown ML problem type';
}
