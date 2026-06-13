# Dataset Type Classification Integration Guide

## Overview

This guide explains how to integrate the dataset type classification API into the frontend upload flow. The classification will automatically run after dataset upload and populate the "Dataset Structure Type" dropdown with the AI-suggested value.

## Implementation Summary

### ✅ Completed Components

1. **Backend API Endpoint** (`/dataset-type-classification`)
   - LLM-powered classification into: time_series, numerical, categorical, mixed
   - Returns confidence score, reasoning, and recommendations

2. **Frontend Service Integration** (`fastApiService.ts`)
   - Added `classifyDatasetType()` method
   - Proper TypeScript interfaces

3. **UI Components Updated**
   - Added "Dataset Structure Type" dropdown to Step1ObjectivesData
   - Dropdown shows AI-suggested value by default
   - User can manually override the suggestion

4. **Type Definitions Updated**
   - Added `dataset_structure_type` to DatasetConfig interface
   - Updated component prop types

## Integration Points

### 1. Upload Flow Integration

The dataset type classification should be called immediately after successful dataset upload. Here's where to integrate it:

```typescript
// In the upload success handler (typically in ModelBuilder.tsx or similar)
const handleDatasetUploadSuccess = async (uploadResponse: FastAPIUploadResponse) => {
  try {
    // Existing upload success logic...
    setActiveDatasetId(uploadResponse.dataset_id);
    
    // NEW: Automatically classify dataset type
    console.log('🤖 Classifying dataset type...');
    const classificationResponse = await fastApiService.classifyDatasetType({
      dataset_id: uploadResponse.dataset_id
    });
    
    if (classificationResponse.success) {
      // Update the dataset config with AI-suggested type
      const updatedConfig = {
        ...datasetConfig,
        dataset_structure_type: classificationResponse.dataset_type
      };
      
      setDatasetConfig(updatedConfig);
      sessionStorage.setItem('dataset_config', JSON.stringify(updatedConfig));
      
      // Optional: Show notification to user
      console.log(`✅ Dataset classified as: ${classificationResponse.dataset_type} (${(classificationResponse.confidence * 100).toFixed(1)}% confidence)`);
      
      // Optional: Add AI message to chat explaining the classification
      const aiMessage = {
        id: `ai-classification-${Date.now()}`,
        type: 'assistant' as const,
        content: `🤖 **Dataset Analysis Complete**\n\n**Type:** ${classificationResponse.dataset_type.replace('_', ' ').toUpperCase()}\n**Confidence:** ${(classificationResponse.confidence * 100).toFixed(1)}%\n\n**Reasoning:** ${classificationResponse.reasoning}\n\n**Recommendations:**\n${classificationResponse.recommendations.map(rec => `• ${rec}`).join('\n')}`,
        timestamp: new Date()
      };
      
      setChatMessages(prev => ({
        ...prev,
        [1]: [...(prev[1] || []), aiMessage]
      }));
    }
  } catch (error) {
    console.error('❌ Dataset type classification failed:', error);
    // Don't fail the upload process, just log the error
    // The dropdown will default to 'mixed' if classification fails
  }
};
```

### 2. Component Props Update

Ensure the Step1ObjectivesData component receives the updated datasetConfig:

```typescript
// In the parent component (ModelBuilder.tsx)
<Step1ObjectivesData
  // ... existing props
  datasetConfig={datasetConfig}
  setDatasetConfig={setDatasetConfig}
  // ... other props
/>
```

### 3. Session Storage Integration

The dataset structure type is already integrated with session storage in the Step1ObjectivesData component, so it will persist across page reloads.

## User Experience Flow

1. **User uploads dataset** → Upload completes successfully
2. **AI classification runs automatically** → API analyzes dataset structure
3. **Dropdown updates** → "Dataset Structure Type" shows AI suggestion with 🤖 indicator
4. **User can override** → Manual selection still possible
5. **AI explanation available** → Classification reasoning shown in chat (optional)

## Error Handling

```typescript
// Classification should be non-blocking
try {
  const classification = await fastApiService.classifyDatasetType({
    dataset_id: datasetId
  });
  // Handle success...
} catch (error) {
  console.warn('Dataset type classification failed, using default:', error);
  // Continue with default 'mixed' type
  // Don't block the user workflow
}
```

## Testing the Integration

### Manual Testing Steps

1. **Upload a time series dataset** (with date columns)
   - Verify classification returns "time_series"
   - Check confidence score is reasonable (>0.7)

2. **Upload a numerical dataset** (mostly continuous variables)
   - Verify classification returns "numerical"
   - Check reasoning mentions numerical variables

3. **Upload a categorical dataset** (mostly discrete variables)
   - Verify classification returns "categorical"
   - Check reasoning mentions categorical variables

4. **Upload a mixed dataset** (both numerical and categorical)
   - Verify classification returns "mixed"
   - Check reasoning mentions both types

5. **Test manual override**
   - Verify user can change the dropdown value
   - Check that manual changes persist in session storage

### API Testing

```bash
# Test the API directly
curl -X POST "http://localhost:8000/api/v1/dataset-type-classification" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"dataset_id": "your_dataset_id"}'
```

## Configuration Options

### Confidence Threshold
You can add a confidence threshold to only auto-populate if the AI is confident:

```typescript
if (classificationResponse.success && classificationResponse.confidence >= 0.8) {
  // Only auto-populate if confidence is high
  setDatasetConfig(prev => ({
    ...prev,
    dataset_structure_type: classificationResponse.dataset_type
  }));
}
```

### User Notification
Add a toast notification when classification completes:

```typescript
// Show success notification
toast.success(`Dataset classified as ${classificationResponse.dataset_type} (${(classificationResponse.confidence * 100).toFixed(1)}% confidence)`);
```

## Troubleshooting

### Common Issues

1. **Classification API returns 404**
   - Ensure dataset_id exists in backend
   - Check authentication token is valid

2. **Classification takes too long**
   - Add timeout to API call (30 seconds recommended)
   - Show loading indicator during classification

3. **Dropdown doesn't update**
   - Check datasetConfig state is properly updated
   - Verify sessionStorage is being written

4. **Manual changes get overwritten**
   - Ensure classification only runs once per upload
   - Don't re-classify on component re-renders

### Debug Logging

Add debug logging to track the flow:

```typescript
console.log('🔍 Starting dataset type classification for:', datasetId);
console.log('📊 Classification result:', classificationResponse);
console.log('💾 Updated config:', updatedConfig);
```

## Future Enhancements

1. **Batch Classification** - Classify multiple datasets at once
2. **Re-classification** - Allow users to re-run classification after data changes
3. **Classification History** - Store classification results for audit trail
4. **Custom Types** - Allow users to define custom dataset types
5. **Confidence Visualization** - Show confidence as a progress bar or color indicator

## API Reference

### Request
```typescript
interface DatasetTypeClassificationRequest {
  dataset_id: string;
}
```

### Response
```typescript
interface DatasetTypeClassificationResponse {
  success: boolean;
  message: string;
  dataset_id: string;
  dataset_type: 'time_series' | 'numerical' | 'categorical' | 'mixed';
  confidence: number; // 0.0 to 1.0
  reasoning: string;
  characteristics: Record<string, any>;
  recommendations: string[];
}
```

## Implementation Checklist

- [x] Backend API endpoint created
- [x] Frontend service method added
- [x] UI dropdown component updated
- [x] TypeScript interfaces defined
- [x] Session storage integration
- [ ] Upload flow integration (needs to be added to ModelBuilder.tsx)
- [ ] Error handling implementation
- [ ] User notification system
- [ ] Testing and validation

## Next Steps

1. **Find the upload success handler** in ModelBuilder.tsx
2. **Add the classification call** after successful upload
3. **Test with different dataset types**
4. **Add user notifications** (optional)
5. **Implement error handling**

The core infrastructure is complete - only the integration into the upload flow remains!

