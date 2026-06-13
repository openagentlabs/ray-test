/**
 * Granular Accuracy Tab Component
 * Displays model performance across different segments with confusion matrices
 */

import React, { useMemo, useState, useEffect } from 'react';
import { BarChart3, Users, TrendingUp } from 'lucide-react';
import { ModelEvaluationData, GranularAccuracy, ColumnStats } from '../../types/modelEvaluation';

// Helper function to clean segment labels
// Returns just "Segment N" - removes all parentheses and their contents
const cleanSegmentLabel = (label: string): string => {
  if (!label) return label;
  
  // Extract just "Segment N" part and return only that
  const segmentMatch = label.match(/^(Segment\s+\d+)/i);
  if (segmentMatch) {
    return segmentMatch[1];
  }
  
  return label;
};

interface GranularAccuracyTabProps {
  evaluationData: Record<string, ModelEvaluationData>;
  comparisonModels: Array<{
    modelName: string;
    modelId: string;
    color: string;
  }>;
}

const GranularAccuracyTab: React.FC<GranularAccuracyTabProps> = ({
  evaluationData,
  comparisonModels
}) => {
  const [selectedVariable, setSelectedVariable] = useState<string>('');
  const [numberOfSegments, setNumberOfSegments] = useState<number>(3);
  const [dataSplit, setDataSplit] = useState<'train' | 'test'>('test');
  
  // Determine default dataSplit: use 'train' if no test data exists, otherwise 'test'
  // Update when evaluationData changes
  useEffect(() => {
    // Check if any model has test granular accuracy data
    const hasTestData = Object.values(evaluationData).some(
      evalData => evalData.granular_accuracy && evalData.granular_accuracy.length > 0
    );
    // Check if any model has train granular accuracy data
    const hasTrainData = Object.values(evaluationData).some(
      evalData => evalData.granular_accuracy_train && evalData.granular_accuracy_train.length > 0
    );
    
    // If no test data but train data exists, switch to 'train'
    if (!hasTestData && hasTrainData && dataSplit === 'test') {
      setDataSplit('train');
    }
    // If test data exists and we're on 'train' but test has data, switch to 'test'
    else if (hasTestData && dataSplit === 'train' && !hasTrainData) {
      setDataSplit('test');
    }
  }, [evaluationData]);

  // Extract all granular accuracy data from backend (filtered by train/test toggle)
  const allGranularData = useMemo(() => {
    const data: Array<GranularAccuracy & { modelId: string; modelName: string }> = [];
    
    Object.entries(evaluationData).forEach(([modelId, evalData]) => {
      const model = comparisonModels.find(m => m.modelId === modelId);
      
      // Select data source based on toggle
      const granularData = dataSplit === 'train' 
        ? (evalData.granular_accuracy_train || [])
        : (evalData.granular_accuracy || []);
      
      if (granularData && granularData.length > 0) {
        granularData.forEach(item => {
          // Ensure all required fields are present from backend
          const granularItem: GranularAccuracy & { modelId: string; modelName: string } = {
            ...item,
            modelId,
            modelName: model?.modelName || 'Unknown',
            // Ensure segment is a string (backend might return it as number)
            segment: String(item.segment || 'Unknown'),
            variable: item.variable || 'Unknown',
            granularity_level: item.granularity_level || 'medium',
            accuracy: item.accuracy || 0,
            precision: item.precision || 0,
            recall: item.recall || 0,
            f1_score: item.f1_score || 0,
            sample_count: item.sample_count || 0,
            confusion_matrix: item.confusion_matrix ?? undefined,
            // Ensure continuous variable flags are preserved
            is_continuous: item.is_continuous ?? false,
            category_value: item.category_value,
            grouped_categories: item.grouped_categories,
            value_range: item.value_range,
            min_value: item.min_value,
            max_value: item.max_value
          };
          data.push(granularItem);
        });
      }
    });
    
    // Debug: Log continuous variables
    const continuousVars = data.filter(d => d.is_continuous === true).map(d => d.variable);
    const uniqueContinuousVars = [...new Set(continuousVars)];
    
    console.log(`Granular accuracy data loaded from backend (${dataSplit}):`, {
      totalItems: data.length,
      models: Object.keys(evaluationData).length,
      segments: [...new Set(data.map(d => d.segment))],
      variables: [...new Set(data.map(d => d.variable))],
      continuousVariables: uniqueContinuousVars,
      sampleContinuousItem: data.find(d => d.is_continuous === true)
    });
    
    return data;
  }, [evaluationData, comparisonModels, dataSplit]);

  // Extract column_stats from evaluationData (from backend's .describe() equivalent)
  const columnStats = useMemo(() => {
    const stats: Record<string, ColumnStats> = {};
    
    // Merge column_stats from all models (they should be the same)
    Object.values(evaluationData).forEach(modelData => {
      if (modelData.column_stats) {
        Object.entries(modelData.column_stats).forEach(([colName, colStats]) => {
          if (!stats[colName]) {
            stats[colName] = colStats as ColumnStats;
          }
        });
      }
    });
    
    console.log('Column stats loaded from backend:', Object.keys(stats).length, 'columns');
    return stats;
  }, [evaluationData]);

  // Get unique variables and granularity levels from backend data
  const availableVariables = useMemo(() => {
    const vars = new Set<string>();
    
    // Include variables present in granular accuracy data
    allGranularData.forEach(item => {
      if (item.variable && item.variable !== 'Unknown') {
        vars.add(item.variable);
      }
    });
    
    // Include all features used to train models (from feature importance)
    Object.values(evaluationData).forEach(modelData => {
      modelData.feature_importance?.forEach(feature => {
        if (feature.feature_name) {
          vars.add(feature.feature_name);
        }
      });
      
      if (Array.isArray(modelData.used_features)) {
        modelData.used_features.forEach(featureName => {
          if (featureName) {
            vars.add(featureName);
          }
        });
      }
    });
    
    const sorted = Array.from(vars).sort();
    console.log('Available variables (features used for training):', sorted);
    return sorted;
  }, [allGranularData, evaluationData]);

  // Set default variable if not set
  React.useEffect(() => {
    if (!selectedVariable && availableVariables.length > 0) {
      console.log('Setting default variable to:', availableVariables[0]);
      setSelectedVariable(availableVariables[0]);
    }
  }, [availableVariables, selectedVariable]);

  // Extract granular data for the selected variable
  const variableSegments = useMemo(() => {
    if (!selectedVariable) return [];
    return allGranularData.filter(item => item.variable === selectedVariable);
  }, [allGranularData, selectedVariable]);

  // Derive available segment counts (granularity levels) for the selected variable
  const availableSegmentCounts = useMemo(() => {
    if (!selectedVariable || variableSegments.length === 0) return [];
    
    // Track unique segment labels per granularity level
    const granularityMap = new Map<number, Set<string>>();
    
    variableSegments.forEach(item => {
      const match = item.granularity_level?.match(/^(\d+)_segments$/);
      if (!match) return;
      
      const expectedCount = parseInt(match[1], 10);
      if (!granularityMap.has(expectedCount)) {
        granularityMap.set(expectedCount, new Set());
      }
      if (item.segment) {
        granularityMap.get(expectedCount)!.add(item.segment);
      }
    });
    
    // Keep any counts that have at least one segment (avoid dropping partial sets)
    const validCounts = Array.from(granularityMap.entries())
      .filter(([, segments]) => segments.size > 0)
      .map(([count]) => count)
      .sort((a, b) => a - b);
    
    return validCounts;
  }, [selectedVariable, variableSegments]);
  
  const maxAvailableSegments = availableSegmentCounts.length > 0
    ? availableSegmentCounts[availableSegmentCounts.length - 1]
    : null;

  // Detect if selected variable is categorical, continuous, or date
  // PRIORITY: Use column_stats from backend (based on original data .describe())
  // FALLBACK: Use heuristics based on segment labels
  const variableType = useMemo(() => {
    if (!selectedVariable) return null;
    
    // First check if backend explicitly marked it as continuous
    const firstItem = variableSegments.find(item => item.variable === selectedVariable);
    if (firstItem) {
      console.log(`🔍 Variable type detection for ${selectedVariable}:`, {
        is_continuous: firstItem.is_continuous,
        category_value: firstItem.category_value,
        grouped_categories: firstItem.grouped_categories,
        value_range: firstItem.value_range,
        min_value: firstItem.min_value,
        max_value: firstItem.max_value
      });
      
      if (firstItem.is_continuous === true) {
        console.log(`✅ Variable ${selectedVariable} detected as continuous from backend is_continuous flag`);
        return 'continuous';
      }
      if (firstItem.is_continuous === false || firstItem.category_value || firstItem.grouped_categories) {
        console.log(`✅ Variable ${selectedVariable} detected as categorical from backend flags`);
        return 'categorical';
      }
    }
    
    // Check if it's a date column by name pattern
    const dateIndicators = ['_d', '_date', 'date_', '_dt', 'issue', 'pymnt', 'credit_pull', 'cr_line'];
    const isDateColumn = dateIndicators.some(ind => selectedVariable.toLowerCase().includes(ind));
    
    // Also check if segments contain month names
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const hasMonthSegments = variableSegments.some(item => 
      monthNames.some(month => item.segment?.includes(`(${month})`))
    );
    
    if (isDateColumn || hasMonthSegments) {
      console.log(`Variable ${selectedVariable} detected as date column`);
      return 'date';
    }
    
    // FIRST: Check column_stats from backend (authoritative source from original data)
    const colStats = columnStats[selectedVariable];
    if (colStats && colStats.variable_type) {
      console.log(`Variable ${selectedVariable} type from column_stats: ${colStats.variable_type}`);
      return colStats.variable_type;
    }
    
    // FALLBACK: Use heuristics if column_stats not available
    if (variableSegments.length === 0) return null;
    
    const segmentLabels = variableSegments
      .map(item => item.segment || '')
      .filter(label => label.length > 0);
    
    if (segmentLabels.length === 0) {
      return null;
    }
    
    const numericRangePattern = /\([\d.-]+-[\d.-]+\)/;
    
    const hasAlphabeticalCategory = segmentLabels.some(label => {
      const cleaned = label
        .replace(/Segment\s+\d+/gi, '')
        .replace(/[()\d\s.,+-]/g, '');
      return /[A-Za-z]/.test(cleaned);
    });
    
    if (hasAlphabeticalCategory) {
      return 'categorical';
    }
    
    const sampleLabel = segmentLabels[0];
    const looksLikeRange = numericRangePattern.test(sampleLabel);
    
    const uniqueSegmentCount = new Set(segmentLabels).size;
    const hasSingleGranularityLevel = availableSegmentCounts.length <= 1;
    const limitedSegments = uniqueSegmentCount <= 10;
    
    // Heuristic: if backend only provided a single granularity level with few segments,
    // treat the variable as categorical even if labels resemble numeric ranges.
    if (hasSingleGranularityLevel && limitedSegments) {
      return 'categorical';
    }
    
    if (looksLikeRange) {
      return 'continuous';
    }
    
    return 'categorical';
  }, [selectedVariable, columnStats, variableSegments, availableSegmentCounts]);

  // Count unique classes for categorical variables
  // Use column_stats if available, otherwise fall back to maxAvailableSegments
  const categoricalClasses = useMemo(() => {
    if (!selectedVariable || variableType !== 'categorical') return null;
    
    // First check column_stats for num_categories (authoritative from original data)
    const colStats = columnStats[selectedVariable];
    if (colStats && colStats.num_categories) {
      console.log(`Categorical classes for ${selectedVariable} from column_stats: ${colStats.num_categories}`);
      // But also check if backend actually has data for that many segments
      // If not, use the max available
      if (availableSegmentCounts.length > 0 && !availableSegmentCounts.includes(colStats.num_categories)) {
        const bestAvailable = maxAvailableSegments || availableSegmentCounts[0];
        console.log(`But backend only has ${bestAvailable} segments, using that instead`);
        return bestAvailable;
      }
      return colStats.num_categories;
    }
    
    // Fallback to maxAvailableSegments from what backend actually generated
    if (maxAvailableSegments) {
      console.log(`Categorical classes for ${selectedVariable} from backend data: ${maxAvailableSegments}`);
      return maxAvailableSegments;
    }
    
    return null;
  }, [selectedVariable, variableType, columnStats, maxAvailableSegments, availableSegmentCounts]);

  // Auto-suggest number of segments when current selection has no data
  React.useEffect(() => {
    // If current selection has no data but there are available options, suggest the best available
    if (selectedVariable && availableSegmentCounts.length > 0 && !availableSegmentCounts.includes(numberOfSegments)) {
      const bestOption = maxAvailableSegments || availableSegmentCounts[0];
      console.log(`Auto-setting segments to ${bestOption} (current ${numberOfSegments} has no data, available: ${availableSegmentCounts.join(', ')})`);
      setNumberOfSegments(bestOption);
    }
    
    // For continuous variables, if 5 segments is available, auto-select it
    if (selectedVariable && variableType === 'continuous' && availableSegmentCounts.includes(5)) {
      if (numberOfSegments !== 5) {
        console.log(`Auto-setting segments to 5 for continuous variable ${selectedVariable}`);
        setNumberOfSegments(5);
      }
    }
  }, [selectedVariable, numberOfSegments, availableSegmentCounts, maxAvailableSegments, variableType]);

  // Filter data by selected variable and number of segments
  const filteredData = useMemo(() => {
    if (!selectedVariable) {
      console.log('No variable selected, returning empty filtered data');
      return [];
    }
    
    // Match granularity_level with the selected number of segments
    const expectedGranularity = `${numberOfSegments}_segments`;
    
    // Get all data for this variable first
    const allForVar = allGranularData.filter(item => item.variable === selectedVariable);
    
    // For continuous variables, if exact match not found, use available granularity level
    if (allForVar.length > 0 && allForVar[0]?.is_continuous) {
      const availableGranularities = [...new Set(allForVar.map(i => i.granularity_level))];
      const hasExactMatch = availableGranularities.includes(expectedGranularity);
      
      if (!hasExactMatch && availableGranularities.length > 0) {
        // Use the available granularity level (should be '5_segments' for continuous)
        const availableGranularity = availableGranularities[0];
        console.log(`⚠️ Continuous variable ${selectedVariable}: No data for ${expectedGranularity}, using available ${availableGranularity}`);
        
        const filtered = allForVar.filter(item => item.granularity_level === availableGranularity);
        if (filtered.length > 0) {
          // Auto-update numberOfSegments to match available data
          const match = availableGranularity.match(/^(\d+)_segments$/);
          if (match) {
            const availableCount = parseInt(match[1], 10);
            if (numberOfSegments !== availableCount) {
              console.log(`Auto-adjusting segments to ${availableCount} for continuous variable`);
              setTimeout(() => setNumberOfSegments(availableCount), 0);
            }
          }
          return filtered;
        }
      }
    }
    
    // Filter by variable and segment count (exact match)
    const filtered = allForVar.filter(item => {
      const granularityMatch = item.granularity_level === expectedGranularity;
      return granularityMatch;
    });
    
    // Debug logging
    if (selectedVariable && filtered.length === 0) {
      console.log(`🔍 No data found for ${selectedVariable} with ${numberOfSegments} segments. Available:`, {
        totalItemsForVar: allForVar.length,
        granularityLevels: [...new Set(allForVar.map(i => i.granularity_level))],
        isContinuous: allForVar[0]?.is_continuous,
        sampleItem: allForVar[0]
      });
    }
    
    // Sort segments by segment number (extract from label) for consistent ordering
    const sorted = filtered.sort((a, b) => {
      // Extract segment number from label (e.g., "Segment 1" -> 1)
      const getSegmentNumber = (label: string): number => {
        const match = label.match(/Segment\s+(\d+)/);
        return match ? parseInt(match[1], 10) : 0;
      };
      return getSegmentNumber(a.segment) - getSegmentNumber(b.segment);
    });
    
    console.log(`Filtered ${sorted.length} items from ${allGranularData.length} total items for ${numberOfSegments} segments (${variableType || 'unknown'} variable)`);
    
    // Debug: Log sample of filtered data for continuous variables
    if (variableType === 'continuous' && sorted.length > 0) {
      console.log(`📊 Continuous variable ${selectedVariable} - Sample filtered items:`, sorted.slice(0, 2).map(item => ({
        segment: item.segment,
        granularity_level: item.granularity_level,
        value_range: item.value_range,
        min_value: item.min_value,
        max_value: item.max_value,
        is_continuous: item.is_continuous
      })));
    }
    
    return sorted;
  }, [allGranularData, selectedVariable, numberOfSegments, variableType]);

  // Group by segment number to avoid duplicates when labels differ across models
  const segmentData = useMemo(() => {
    const segments = new Map<
      string,
      {
        label: string;
        items: Array<GranularAccuracy & { modelId: string; modelName: string }>;
      }
    >();
    
    filteredData.forEach(item => {
      const match = item.segment?.match(/Segment\s+(\d+)/);
      const key = match ? `segment_${match[1]}` : item.segment || 'Unknown';
      
      if (!segments.has(key)) {
        segments.set(key, {
          label: item.segment || `Segment ${match?.[1] || '?'}`,
          items: []
        });
      }
      
      segments.get(key)!.items.push(item);
    });
    
    // Convert to array and sort by segment number to maintain consistent ordering
    const segmentArray = Array.from(segments.entries()).map(([key, data]) => {
      const sortedItems = data.items.sort((a, b) => {
        const order = comparisonModels.map(m => m.modelName);
        return order.indexOf(a.modelName) - order.indexOf(b.modelName);
      });
      
      // Calculate average accuracy for this segment
      const avgAccuracy = sortedItems.reduce((sum, item) => sum + item.accuracy, 0) / sortedItems.length;
      
      return {
        key,
        segment: cleanSegmentLabel(data.label),  // Clean the label - remove numeric ranges
        items: sortedItems,
        avgAccuracy
      };
    });
    
    const sortedSegments = segmentArray.sort((a, b) => {
      const getSegmentNumber = (segmentKey: string): number => {
        const match = segmentKey.match(/segment_(\d+)/);
        return match ? parseInt(match[1], 10) : 0;
      };
      
      const numA = getSegmentNumber(a.key);
      const numB = getSegmentNumber(b.key);
      
      if (numA === numB) {
        return b.avgAccuracy - a.avgAccuracy;
      }
      
      return numA - numB;
    });
    
    // For continuous variables, show all segments (always 5), don't limit
    // For categorical, limit to selected number
    const shouldLimit = variableType !== 'continuous';
    const limitedSegments = shouldLimit 
      ? sortedSegments.slice(0, numberOfSegments)
      : sortedSegments;  // Show all segments for continuous variables
    
    // Debug: Log segment data for continuous variables
    if (limitedSegments.length > 0 && filteredData.length > 0 && filteredData[0]?.is_continuous) {
      console.log(`📈 Continuous variable segmentData:`, {
        totalSegments: limitedSegments.length,
        segments: limitedSegments.map(s => ({
          segment: s.segment,
          itemsCount: s.items.length,
          firstItem: s.items[0] ? {
            value_range: s.items[0].value_range,
            min_value: s.items[0].min_value,
            max_value: s.items[0].max_value
          } : null
        }))
      });
    }
    
    return limitedSegments.map(({ segment, items }) => ({ segment, items }));
  }, [filteredData, comparisonModels, numberOfSegments, variableType]);

  // Calculate averages for table
  const accuracyTable = useMemo(() => {
    const table: Array<{
      segment: string;
      modelAccuracies: Record<string, { accuracy: number; sampleCount: number }>;
      average: number;
    }> = [];

    segmentData.forEach(({ segment, items }) => {
      const modelAccuracies: Record<string, { accuracy: number; sampleCount: number }> = {};
      let totalAccuracy = 0;
      let count = 0;

      items.forEach(item => {
        modelAccuracies[item.modelName] = {
          accuracy: item.accuracy,
          sampleCount: item.sample_count
        };
        totalAccuracy += item.accuracy;
        count++;
      });

      table.push({
        segment,
        modelAccuracies,
        average: count > 0 ? totalAccuracy / count : 0
      });
    });

    return table;
  }, [segmentData]);

  // Calculate performance metrics by segment
  const segmentMetrics = useMemo(() => {
    return segmentData.map(({ segment, items }) => {
      let totalPrecision = 0;
      let totalRecall = 0;
      let totalF1 = 0;
      let count = 0;

      items.forEach(item => {
        totalPrecision += item.precision || 0;
        totalRecall += item.recall || 0;
        totalF1 += item.f1_score || 0;
        count++;
      });

      return {
        segment,
        precision: count > 0 ? totalPrecision / count : 0,
        recall: count > 0 ? totalRecall / count : 0,
        f1Score: count > 0 ? totalF1 / count : 0
      };
    });
  }, [segmentData]);

  // Calculate sample distribution
  const sampleDistribution = useMemo(() => {
    const distribution: Array<{ segment: string; count: number; percentage: number }> = [];
    let totalSamples = 0;

    segmentData.forEach(({ segment, items }) => {
      // Use sample count from first model (all models use same test data, so counts should be identical)
      // If multiple models have different counts, use the first non-zero count
      const segmentCount = items.length > 0 
        ? (items.find(item => item.sample_count > 0)?.sample_count || items[0].sample_count || 0)
        : 0;
      
      totalSamples += segmentCount;
      distribution.push({ segment, count: segmentCount, percentage: 0 });
    });

    // Calculate percentages
    distribution.forEach(item => {
      item.percentage = totalSamples > 0 ? (item.count / totalSamples) * 100 : 0;
    });

    return distribution;
  }, [segmentData]);

  // Debug: Log evaluation data structure
  React.useEffect(() => {
    console.log('=== Granular Accuracy Tab Debug ===');
    console.log('Evaluation Data Keys:', Object.keys(evaluationData));
    console.log('Comparison Models:', comparisonModels);
    console.log('All Granular Data Count:', allGranularData.length);
    console.log('Available Variables:', availableVariables);
    console.log('Selected Variable:', selectedVariable);
    console.log('Variable Type:', variableType);
    console.log('Available Segment Counts:', availableSegmentCounts);
    console.log('Max Available Segments:', maxAvailableSegments);
    console.log('Categorical Classes:', categoricalClasses);
    console.log('Number of Segments:', numberOfSegments);
    console.log('Expected Granularity:', `${numberOfSegments}_segments`);
    console.log('Filtered Data Count:', filteredData.length);
    console.log('Segment Data:', segmentData);
    
    // Log sample of evaluation data
    Object.entries(evaluationData).forEach(([modelId, data]) => {
      console.log(`Model ${modelId}:`, {
        hasGranularAccuracy: !!data.granular_accuracy,
        granularAccuracyLength: data.granular_accuracy?.length || 0,
        sampleGranular: data.granular_accuracy?.[0] || null
      });
    });
    
    // Log all granular data for selected variable
    if (selectedVariable) {
      const variableData = allGranularData.filter(item => item.variable === selectedVariable);
      console.log(`Data for ${selectedVariable}:`, variableData);
    }
  }, [evaluationData, comparisonModels, allGranularData, availableVariables, selectedVariable, variableType, availableSegmentCounts, maxAvailableSegments, categoricalClasses, numberOfSegments, filteredData, segmentData]);

  // Log evaluation data structure for debugging
  useEffect(() => {
    if (allGranularData.length === 0) {
      console.warn('Granular Accuracy Debug - No data found:', {
        evaluationDataKeys: Object.keys(evaluationData),
        sampleEvaluationData: Object.entries(evaluationData).map(([id, data]) => ({
          modelId: id,
          hasGranularAccuracy: 'granular_accuracy' in data,
          granularAccuracyType: typeof data.granular_accuracy,
          granularAccuracyLength: Array.isArray(data.granular_accuracy) ? data.granular_accuracy.length : 'not array',
          granularAccuracyValue: data.granular_accuracy,
          hasGranularAccuracyTrain: 'granular_accuracy_train' in data,
          problemType: data.problem_type,
          dataSplit
        }))[0]
      });
    }
  }, [allGranularData.length, evaluationData, dataSplit]);

  if (allGranularData.length === 0) {
    const classificationModels = Object.entries(evaluationData).filter(([_, data]) => {
      const problemType = data.problem_type || data.model?.task_type || 'unknown';
      return problemType === 'classification';
    });
    const regressionModels = Object.entries(evaluationData).filter(([_, data]) => {
      const problemType = data.problem_type || data.model?.task_type || 'unknown';
      return problemType === 'regression';
    });
    
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-200">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Granular Accuracy Analysis</h2>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
            <p className="text-yellow-800 font-semibold mb-2">⚠️ No granular accuracy data available</p>
            <p className="text-yellow-700 text-sm mb-2">
              The selected models don't have granular accuracy data yet. This data is generated during model evaluation.
            </p>
            {regressionModels.length > 0 && (
              <div className="bg-blue-50 border border-blue-200 rounded p-3 mb-2">
                <p className="text-blue-800 text-sm">
                  <strong>Note:</strong> {regressionModels.length} of your {Object.keys(evaluationData).length} models are <strong>regression</strong> models. 
                  Granular accuracy is only available for <strong>classification</strong> models.
                </p>
              </div>
            )}
            {classificationModels.length > 0 && (
              <div className="bg-red-50 border border-red-200 rounded p-3 mb-2">
                <p className="text-red-800 text-sm">
                  <strong>Issue detected:</strong> You have {classificationModels.length} classification model(s) but no granular accuracy data. 
                  This suggests the calculation may have failed. Check backend logs for details.
                </p>
              </div>
            )}
            <div className="text-yellow-700 text-sm">
              <p className="font-semibold mb-1">To generate granular accuracy data:</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>Train new models - granular accuracy is calculated automatically</li>
                <li>Or regenerate MEEA evaluation for existing models</li>
                <li>Check backend logs for calculation errors (look for "⚠️ No granular accuracy data generated!")</li>
              </ul>
            </div>
          </div>
          <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600">
            <p className="font-semibold mb-2">Debug Info:</p>
            <p>Models loaded: {Object.keys(evaluationData).length}</p>
            <p>Models with data: {Object.entries(evaluationData).filter(([_, data]) => {
              const granularData = dataSplit === 'train' 
                ? (data.granular_accuracy_train || [])
                : (data.granular_accuracy || []);
              return granularData && granularData.length > 0;
            }).length}</p>
            <div className="mt-3 space-y-1">
              <p className="font-semibold">Per-model details:</p>
              {Object.entries(evaluationData).map(([modelId, data]) => {
                const granularData = dataSplit === 'train' 
                  ? (data.granular_accuracy_train || [])
                  : (data.granular_accuracy || []);
                const hasData = granularData && granularData.length > 0;
                const problemType = data.problem_type || data.model?.task_type || 'unknown';
                return (
                  <div key={modelId} className="text-xs border-l-2 pl-2 border-gray-300">
                    <span className="font-mono">{modelId.substring(0, 8)}...</span>: 
                    {hasData ? (
                      <span className="text-green-600"> {granularData.length} segments</span>
                    ) : (
                      <span className="text-red-600"> No data</span>
                    )}
                    {!hasData && (
                      <span className="text-gray-500"> (type: {problemType}, granular_accuracy: {Array.isArray(data.granular_accuracy) ? `[] (empty)` : data.granular_accuracy === null ? 'null' : data.granular_accuracy === undefined ? 'undefined' : typeof data.granular_accuracy})</span>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="mt-3 text-xs text-gray-500">
              Note: Granular accuracy is only available for classification models. 
              If all models show "No data", check backend logs for calculation errors.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold text-gray-900">Granular Accuracy Analysis</h2>
          {/* Train/Test Toggle */}
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-gray-700">Data Split:</span>
            <div className="flex bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => setDataSplit('train')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  dataSplit === 'train'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Train
              </button>
              <button
                onClick={() => setDataSplit('test')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  dataSplit === 'test'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Test
              </button>
            </div>
          </div>
        </div>
        <p className="text-gray-600">
          Examine model performance across different data segments and granularity levels. 
          Use the toggle above to switch between Train and Test data splits from model training.
        </p>
      </div>

      {/* Segment Information Dropdown */}
      {segmentData.length > 0 && (
        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
          <h3 className="text-lg font-bold text-gray-900 mb-4">Segment Information - {selectedVariable}</h3>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              View Segment Details
            </label>
            <select
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              onChange={(e) => {
                const selectedSegment = e.target.value;
                if (selectedSegment) {
                  // Scroll to the selected segment
                  const element = document.getElementById(`segment-${selectedSegment}`);
                  if (element) {
                    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }
                }
              }}
              defaultValue=""
            >
              <option value="">Select a segment to view details</option>
              {segmentData.map(({ segment, items }, idx) => {
                const firstItem = items[0];
                let segmentInfo = '';
                
                // Debug logging
                if (idx === 0) {
                  console.log('🔍 First segment data:', {
                    segment,
                    category_value: firstItem.category_value,
                    grouped_categories: firstItem.grouped_categories,
                    variable: firstItem.variable,
                    allKeys: Object.keys(firstItem)
                  });
                }
                
                if (variableType === 'categorical') {
                  // For categorical: show category value
                  if (firstItem.category_value) {
                    segmentInfo = firstItem.category_value;
                  } else if (firstItem.grouped_categories && firstItem.grouped_categories.length > 0) {
                    // For grouped categories
                    if (firstItem.grouped_categories.length <= 3) {
                      segmentInfo = firstItem.grouped_categories.join(', ');
                    } else {
                      segmentInfo = `${firstItem.grouped_categories[0]}, +${firstItem.grouped_categories.length - 1} more`;
                    }
                  } else {
                    // Fallback: extract from segment label
                    const match = segment.match(/\(([^)]+)\)/);
                    segmentInfo = match ? match[1] : segment;
                  }
                } else if (variableType === 'continuous') {
                  // For continuous: show value range
                  if (firstItem.value_range) {
                    segmentInfo = firstItem.value_range;
                  } else if (firstItem.min_value !== undefined && firstItem.max_value !== undefined) {
                    // Format range from min/max
                    const min = Number.isInteger(firstItem.min_value) 
                      ? firstItem.min_value 
                      : firstItem.min_value.toFixed(2);
                    const max = Number.isInteger(firstItem.max_value) 
                      ? firstItem.max_value 
                      : firstItem.max_value.toFixed(2);
                    segmentInfo = `${min} to ${max}`;
                  } else {
                    // Fallback: extract from segment label
                    const match = segment.match(/\(([^)]+)\)/);
                    segmentInfo = match ? match[1] : segment;
                  }
                } else {
                  // Fallback: use segment label
                  segmentInfo = segment;
                }
                
                return (
                  <option key={idx} value={segment}>
                    {segment}: {segmentInfo}
                  </option>
                );
              })}
            </select>
          </div>
          
          {/* Display all segments with their information */}
          <div className="mt-4 space-y-2">
            <p className="text-sm font-semibold text-gray-700 mb-2">All Segments and Their {variableType === 'categorical' ? 'Categories' : 'Intervals'}:</p>
            <div className="space-y-2">
              {segmentData.map(({ segment, items }, idx) => {
                const firstItem = items[0];
                let segmentInfo = '';
                let infoType = '';
                
                if (variableType === 'categorical') {
                  if (firstItem.category_value) {
                    segmentInfo = firstItem.category_value;
                    infoType = 'Category';
                  } else if (firstItem.grouped_categories && firstItem.grouped_categories.length > 0) {
                    if (firstItem.grouped_categories.length <= 3) {
                      segmentInfo = firstItem.grouped_categories.join(', ');
                    } else {
                      segmentInfo = `${firstItem.grouped_categories[0]}, +${firstItem.grouped_categories.length - 1} more`;
                    }
                    infoType = 'Grouped Categories';
                  } else {
                    const match = segment.match(/\(([^)]+)\)/);
                    segmentInfo = match ? match[1] : segment;
                    infoType = 'Category';
                  }
                } else if (variableType === 'continuous') {
                  if (firstItem.value_range) {
                    segmentInfo = firstItem.value_range;
                    infoType = 'Range';
                  } else if (firstItem.min_value !== undefined && firstItem.max_value !== undefined) {
                    const min = Number.isInteger(firstItem.min_value) 
                      ? firstItem.min_value 
                      : firstItem.min_value.toFixed(2);
                    const max = Number.isInteger(firstItem.max_value) 
                      ? firstItem.max_value 
                      : firstItem.max_value.toFixed(2);
                    segmentInfo = `${min} to ${max}`;
                    infoType = 'Range';
                  } else {
                    const match = segment.match(/\(([^)]+)\)/);
                    segmentInfo = match ? match[1] : segment;
                    infoType = 'Range';
                  }
                } else {
                  segmentInfo = segment;
                  infoType = 'Info';
                }
                
                return (
                  <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-gray-900">{segment}:</span>
                      <span className="text-gray-700">{segmentInfo}</span>
                    </div>
                    <span className="text-xs text-gray-500 bg-white px-2 py-1 rounded border border-gray-300">
                      {infoType}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select Variable (Base for Segmentation)
            </label>
            <select
              value={selectedVariable}
              onChange={(e) => setSelectedVariable(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {availableVariables.map(variable => (
                <option key={variable} value={variable}>{variable}</option>
              ))}
            </select>
            {selectedVariable && variableType && (
              <p className="mt-2 text-xs text-gray-500">
                Variable type: <span className="font-semibold capitalize">{variableType}</span>
                {variableType === 'continuous' 
                  ? ` (${columnStats[selectedVariable]?.unique_count || 'many'} unique values)`
                  : categoricalClasses 
                    ? ` (${categoricalClasses} categories)`
                    : ''}
              </p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Number of Segments
            </label>
            <select
              value={numberOfSegments}
              onChange={(e) => setNumberOfSegments(Number(e.target.value))}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {/* Add the categorical class count if it's ≤5 and not in the default list */}
              {variableType === 'categorical' && categoricalClasses && categoricalClasses <= 5 && ![2, 3, 4, 5].includes(categoricalClasses) && (
                <option value={categoricalClasses}>{categoricalClasses}</option>
              )}
              <option value={2}>2</option>
              <option value={3}>3</option>
              <option value={4}>4</option>
              <option value={5}>5</option>
            </select>
            {/* Variable Type Badge */}
            {selectedVariable && variableType && (
              <div className="mt-3 flex items-center gap-2">
                <span className="text-sm font-medium text-gray-700">Variable Type:</span>
                {variableType === 'categorical' && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-blue-100 text-blue-800 border border-blue-300">
                    📊 CATEGORICAL
                  </span>
                )}
                {variableType === 'continuous' && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-green-100 text-green-800 border border-green-300">
                    📈 CONTINUOUS
                  </span>
                )}
                {variableType === 'date' && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-indigo-100 text-indigo-800 border border-indigo-300">
                    📅 DATE
                  </span>
                )}
              </div>
            )}
            
            {/* Detailed explanation */}
            {selectedVariable && variableType === 'categorical' && categoricalClasses && (
              <div className="mt-2 p-2 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-xs text-blue-800">
                  Detected as categorical because: <span className="font-semibold">
                    {columnStats[selectedVariable]?.dtype === 'object' 
                      ? 'String/text data type' 
                      : `Only ${categoricalClasses} unique values (≤15)`}
                  </span>
                </p>
                <p className="text-xs text-blue-700 mt-1">
                  {categoricalClasses <= 5 
                    ? `Each category gets its own segment. You can select 2-5 segments.`
                    : `${categoricalClasses} categories grouped into ${numberOfSegments} divisions.`
                  }
                </p>
              </div>
            )}
            {selectedVariable && variableType === 'continuous' && (
              <div className="mt-2 p-2 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-xs text-green-800">
                  Detected as continuous because: <span className="font-semibold">Numeric data with many unique values (&gt;15)</span>
                </p>
                <p className="text-xs text-green-700 mt-1">
                  Data divided into <span className="font-semibold">{numberOfSegments} equal-frequency quantile bins</span>
                </p>
              </div>
            )}
            {selectedVariable && variableType === 'date' && (
              <div className="mt-2 p-2 bg-indigo-50 border border-indigo-200 rounded-lg">
                <p className="text-xs text-indigo-800">
                  Detected as date because: <span className="font-semibold">Column name or values indicate date format</span>
                </p>
                <p className="text-xs text-indigo-700 mt-1">
                  Data divided into <span className="font-semibold">{numberOfSegments} month-based segments</span> (e.g., Jan-Jun, Jul-Dec)
                </p>
              </div>
            )}
            {selectedVariable && availableSegmentCounts.length > 0 && maxAvailableSegments && maxAvailableSegments < 5 && (
              <div className="mt-2 p-2 bg-orange-50 border border-orange-200 rounded-lg">
                <p className="text-xs text-orange-800">
                  ⚠️ <span className="font-semibold">This variable can have at most {maxAvailableSegments} segment{maxAvailableSegments === 1 ? '' : 's'}</span>
                </p>
                <p className="text-xs text-orange-700 mt-1">
                  Due to data distribution (many duplicate or similar values), fewer bins could be created.
                  {availableSegmentCounts.length > 1 && ` Available: ${availableSegmentCounts.join(', ')} segments.`}
                </p>
              </div>
            )}
            {selectedVariable && availableSegmentCounts.length > 0 && maxAvailableSegments && maxAvailableSegments >= 5 && (
              <p className="mt-2 text-xs text-gray-500">
                ✓ This variable supports up to <span className="font-semibold">{maxAvailableSegments} segments</span>
                {availableSegmentCounts.length > 1 && ` (available: ${availableSegmentCounts.join(', ')})`}
              </p>
            )}
            {selectedVariable && availableSegmentCounts.length > 0 && !availableSegmentCounts.includes(numberOfSegments) && (
              <div className="mt-2 p-2 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-xs text-yellow-800">
                  Selected {numberOfSegments} segments is not available. Please select: {availableSegmentCounts.join(', ')}
                </p>
              </div>
            )}
            {selectedVariable && availableSegmentCounts.length === 0 && (
              <div className="mt-2 p-2 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-xs text-yellow-800 font-semibold">
                  ⚠️ No granular accuracy data for <span className="font-bold">{selectedVariable}</span>
                </p>
                {/* Check if column is completely empty (100% missing) */}
                {columnStats[selectedVariable] && (columnStats[selectedVariable].missing_pct === 100 || columnStats[selectedVariable].unique_count === 0) ? (
                  <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded">
                    <p className="text-xs text-red-800 font-bold">
                      🚫 This column has NO DATA (100% missing values)
                    </p>
                    <p className="text-xs text-red-700 mt-1">
                      All {columnStats[selectedVariable].total_count?.toLocaleString() || 'N/A'} rows have null/empty values for this column.
                      It cannot be used for segmentation.
                    </p>
                    <p className="text-xs text-red-600 mt-1 italic">
                      Please select a different variable that contains actual data.
                    </p>
                  </div>
                ) : columnStats[selectedVariable] ? (
                  <>
                    <p className="text-xs text-yellow-700 mt-1">
                      This variable is <span className="font-semibold">{columnStats[selectedVariable].variable_type}</span> 
                      {columnStats[selectedVariable].variable_type === 'categorical' 
                        ? ` with ${columnStats[selectedVariable].num_categories || columnStats[selectedVariable].unique_count} categories`
                        : ` (${columnStats[selectedVariable].unique_count} unique values)`
                      }, but no segment data was generated.
                    </p>
                    {columnStats[selectedVariable].missing_pct && columnStats[selectedVariable].missing_pct > 50 && (
                      <p className="text-xs text-orange-700 mt-1 font-semibold">
                        ⚠️ High missing rate: {columnStats[selectedVariable].missing_pct.toFixed(1)}% of values are null
                      </p>
                    )}
                    <p className="text-xs text-yellow-700 mt-1">
                      Possible reasons:
                    </p>
                    <ul className="text-xs text-yellow-700 ml-3 list-disc">
                      <li>Too many duplicate values to create distinct bins</li>
                      <li>Date column not properly converted</li>
                      <li>Data quality issues during evaluation</li>
                    </ul>
                  </>
                ) : (
                  <>
                    <p className="text-xs text-yellow-700 mt-1">
                      This can happen if:
                    </p>
                    <ul className="text-xs text-yellow-700 mt-1 ml-3 list-disc">
                      <li>The variable wasn't included in the model's training features</li>
                      <li>It's a date column that wasn't converted to numeric</li>
                      <li>It has too few unique values (less than 2)</li>
                      <li>Most values are duplicates (can't create distinct bins)</li>
                      <li><strong>The column may be completely empty (100% null)</strong></li>
                    </ul>
                  </>
                )}
                <p className="text-xs text-yellow-600 mt-2 italic">
                  Re-train the model with this variable included to generate segment data.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Accuracy Table */}
      {accuracyTable.length > 0 && (
        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
          <h3 className="text-xl font-bold text-gray-900 mb-4">
            Accuracy by Segment - {selectedVariable}
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b-2 border-gray-200">
                  <th className="px-4 py-3 text-left font-semibold text-gray-700">Segment</th>
                  {comparisonModels.map(model => (
                    <th key={model.modelId} className="px-4 py-3 text-center font-semibold text-gray-700">
                      {model.modelName}
                    </th>
                  ))}
                  <th className="px-4 py-3 text-center font-semibold text-gray-700">Average</th>
                </tr>
              </thead>
              <tbody>
                {accuracyTable.map((row, idx) => (
                  <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    <td className="px-4 py-3 font-medium text-gray-900">{row.segment}</td>
                    {comparisonModels.map(model => {
                      const modelData = row.modelAccuracies[model.modelName];
                      return (
                        <td key={model.modelId} className="px-4 py-3 text-center">
                          {modelData ? (
                            <div>
                              <span className="font-semibold text-gray-900">
                                {(modelData.accuracy * 100).toFixed(2)}%
                              </span>
                              <span className="text-xs text-gray-500 ml-1">
                                (n={modelData.sampleCount})
                              </span>
                            </div>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                      );
                    })}
                    <td className="px-4 py-3 text-center font-semibold text-blue-600">
                      {(row.average * 100).toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Performance Metrics and Sample Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Performance Metrics */}
        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-blue-600" />
            <h3 className="text-lg font-bold text-gray-900">Performance Metrics</h3>
          </div>
          <div className="space-y-4">
            {segmentMetrics.map((metric, idx) => (
              <div key={idx} className="border-b border-gray-200 pb-3 last:border-b-0">
                <div className="font-semibold text-gray-900 mb-2">{metric.segment}</div>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <div className="text-gray-600">Precision</div>
                    <div className="font-semibold text-gray-900">
                      {(metric.precision * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-600">Recall</div>
                    <div className="font-semibold text-gray-900">
                      {(metric.recall * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-600">F1 Score</div>
                    <div className="font-semibold text-gray-900">
                      {(metric.f1Score * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Sample Distribution */}
        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
          <div className="flex items-center gap-2 mb-4">
            <Users className="w-5 h-5 text-green-600" />
            <h3 className="text-lg font-bold text-gray-900">Sample Distribution</h3>
          </div>
          <div className="space-y-4">
            {sampleDistribution.map((dist, idx) => (
              <div key={idx}>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm font-medium text-gray-900">{dist.segment}</span>
                  <span className="text-sm text-gray-600">
                    {dist.count} ({dist.percentage.toFixed(1)}%)
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div
                    className="bg-green-500 h-3 rounded-full transition-all"
                    style={{ width: `${dist.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Confusion Matrices by Segment */}
      {segmentData.map(({ segment, items }) => {
        const firstItem = items[0];
        let segmentInfo = '';
        
        if (variableType === 'categorical') {
          if (firstItem.category_value) {
            segmentInfo = firstItem.category_value;
          } else if (firstItem.grouped_categories && firstItem.grouped_categories.length > 0) {
            if (firstItem.grouped_categories.length <= 3) {
              segmentInfo = firstItem.grouped_categories.join(', ');
            } else {
              segmentInfo = `${firstItem.grouped_categories[0]}, +${firstItem.grouped_categories.length - 1} more`;
            }
          }
        } else if (variableType === 'continuous') {
          if (firstItem.value_range) {
            segmentInfo = firstItem.value_range;
          } else if (firstItem.min_value !== undefined && firstItem.max_value !== undefined) {
            const min = Number.isInteger(firstItem.min_value) 
              ? firstItem.min_value 
              : firstItem.min_value.toFixed(2);
            const max = Number.isInteger(firstItem.max_value) 
              ? firstItem.max_value 
              : firstItem.max_value.toFixed(2);
            segmentInfo = `${min} to ${max}`;
          }
        }
        
        return (
        <div key={segment} id={`segment-${segment}`} className="bg-white rounded-xl shadow-lg p-6 border border-gray-200">
          <div className="mb-6">
            <h3 className="text-xl font-bold text-gray-900">Segment: {segment}</h3>
            {segmentInfo && (
              <p className="text-sm text-gray-600 mt-1">
                {variableType === 'categorical' ? 'Category' : 'Interval'}: <span className="font-semibold text-gray-900">{segmentInfo}</span>
              </p>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            {items.map((item, idx) => {
              return (
                <div key={idx} className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                  <div className="mb-3">
                    <div className="font-semibold text-gray-900">{item.modelName}</div>
                    <div className="text-sm text-gray-600">Total: {item.sample_count} samples</div>
                    <div className="text-sm font-semibold text-blue-600 mt-1">
                      Accuracy: {(item.accuracy * 100).toFixed(1)}%
                    </div>
                  </div>
                  {item.confusion_matrix && item.confusion_matrix.length > 0 ? (
                    <div className="mt-4 bg-white rounded border border-gray-200 p-3">
                      <div className="text-xs text-gray-600 mb-2 font-medium">Predicted</div>
                      <table className="w-full text-xs border-collapse">
                        <thead>
                          <tr>
                            <th className="border p-1 bg-gray-50"></th>
                            <th className="border p-1 bg-gray-50 text-center">Neg</th>
                            <th className="border p-1 bg-gray-50 text-center">Pos</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <th className="border p-1 bg-gray-50 text-left">Neg</th>
                            <td className="border p-2 text-center bg-green-50">
                              <div className="font-semibold">{item.confusion_matrix[0]?.[0] || 0}</div>
                              <div className="text-gray-600">
                                ({item.sample_count > 0 ? ((item.confusion_matrix[0]?.[0] || 0) / item.sample_count * 100).toFixed(1) : '0.0'}%)
                              </div>
                              <div className="text-xs text-gray-500 mt-1">TN</div>
                            </td>
                            <td className="border p-2 text-center bg-red-50">
                              <div className="font-semibold">{item.confusion_matrix[0]?.[1] || 0}</div>
                              <div className="text-gray-600">
                                ({item.sample_count > 0 ? ((item.confusion_matrix[0]?.[1] || 0) / item.sample_count * 100).toFixed(1) : '0.0'}%)
                              </div>
                              <div className="text-xs text-gray-500 mt-1">FP</div>
                            </td>
                          </tr>
                          <tr>
                            <th className="border p-1 bg-gray-50 text-left">Pos</th>
                            <td className="border p-2 text-center bg-red-50">
                              <div className="font-semibold">{item.confusion_matrix[1]?.[0] || 0}</div>
                              <div className="text-gray-600">
                                ({item.sample_count > 0 ? ((item.confusion_matrix[1]?.[0] || 0) / item.sample_count * 100).toFixed(1) : '0.0'}%)
                              </div>
                              <div className="text-xs text-gray-500 mt-1">FN</div>
                            </td>
                            <td className="border p-2 text-center bg-green-50">
                              <div className="font-semibold">{item.confusion_matrix[1]?.[1] || 0}</div>
                              <div className="text-gray-600">
                                ({item.sample_count > 0 ? ((item.confusion_matrix[1]?.[1] || 0) / item.sample_count * 100).toFixed(1) : '0.0'}%)
                              </div>
                              <div className="text-xs text-gray-500 mt-1">TP</div>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="mt-4 p-4 bg-white rounded border border-gray-200 text-center text-gray-500">
                      <div className="text-sm mb-2 font-medium">Predicted</div>
                      <div className="text-xs text-gray-400">No confusion matrix data</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        );
      })}

      {/* Links */}
      <div className="flex gap-4">
        <button className="flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors">
          <BarChart3 className="w-4 h-4" />
          <span>Performance Metrics</span>
        </button>
        <button className="flex items-center gap-2 px-4 py-2 bg-green-50 text-green-600 rounded-lg hover:bg-green-100 transition-colors">
          <Users className="w-4 h-4" />
          <span>Sample Distribution</span>
        </button>
      </div>
    </div>
  );
};

export default GranularAccuracyTab;



