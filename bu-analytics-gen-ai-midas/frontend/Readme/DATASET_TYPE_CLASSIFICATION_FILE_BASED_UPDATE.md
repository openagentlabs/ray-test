# Dataset Type Classification - File-Based API Update

## 🎯 Problem Solved

Updated the dataset type classification API to work with **file uploads** instead of `dataset_id`, since classification should happen **before** the dataset is uploaded and gets an ID.

## 📋 Changes Made

### ✅ Backend Updates

1. **API Endpoint** (`backend/app/api/routes.py`)
   - Changed from `POST /dataset-type-classification` with JSON body
   - To `POST /dataset-type-classification` with file upload
   - Now accepts `UploadFile` parameter instead of `dataset_id`
   - Reads CSV file directly from upload stream
   - Returns classification without requiring existing dataset

2. **Pydantic Schemas** (`backend/app/models/schemas.py`)
   - Updated `DatasetTypeClassificationRequest` to handle file uploads
   - Made `dataset_id` optional in response (empty string for file-based classification)
   - Added proper field descriptions

### ✅ Frontend Updates

1. **Service Interface** (`frontend/src/services/fastApiService.ts`)
   - Changed request interface to accept `File` instead of `dataset_id`
   - Updated service method to send `FormData` with file upload
   - Made `dataset_id` optional in response interface

2. **Integration Utilities** (`frontend/src/utils/datasetTypeIntegration.ts`)
   - Updated `classifyAndUpdateDatasetConfig()` to accept `File` parameter
   - Changed caching logic to use filename instead of dataset_id
   - Added `handleFileClassificationBeforeUpload()` for pre-upload classification
   - Updated helper functions to work with files

## 🔄 New API Flow

### Before (Dataset ID Based)
```
1. Upload file → Get dataset_id
2. Call classification API with dataset_id
3. Update dropdown with result
```

### After (File Based)
```
1. User selects file
2. Call classification API with file
3. Update dropdown with result
4. Upload file (classification already done)
```

## 🧪 API Usage

### New API Call
```bash
curl -X POST "http://localhost:8000/api/v1/dataset-type-classification" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@dataset.csv"
```

### Frontend Integration
```typescript
// Before upload - classify the file
const classificationResult = await fastApiService.classifyDatasetType({
  file: selectedFile
});

// Update the dropdown with AI suggestion
if (classificationResult.success) {
  setDatasetConfig(prev => ({
    ...prev,
    dataset_structure_type: classificationResult.dataset_type
  }));
}

// Then proceed with normal upload
```

### Using Helper Function
```typescript
import { handleFileClassificationBeforeUpload } from '@/utils/datasetTypeIntegration';

// When user selects a file
const handleFileSelect = async (file: File) => {
  // Classify the file before upload
  await handleFileClassificationBeforeUpload(
    file,
    datasetConfig,
    setDatasetConfig,
    setChatMessages,
    showNotification
  );
  
  // File classification is now complete
  // User can see AI suggestion in dropdown
  // Then proceed with upload when ready
};
```

## 🎨 User Experience

1. **File Selection** → User picks CSV file
2. **Instant Analysis** → AI analyzes file content immediately  
3. **Smart Suggestion** → Dropdown shows AI-suggested ML problem type
4. **User Control** → User can accept or override suggestion
5. **Upload** → File gets uploaded with pre-determined type

## 🔧 Integration Points

### When to Call the API

**Call BEFORE upload when:**
- User selects a file in file picker
- User drags and drops a file
- File is loaded into the interface

**Example Integration:**
```typescript
// In file selection handler
const onFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
  const file = event.target.files?.[0];
  if (file && file.name.endsWith('.csv')) {
    // Classify immediately
    const result = await fastApiService.classifyDatasetType({ file });
    
    if (result.success) {
      // Update dropdown
      setDatasetConfig(prev => ({
        ...prev,
        dataset_structure_type: result.dataset_type
      }));
      
      // Show confidence to user
      console.log(`AI suggests: ${result.dataset_type} (${result.confidence * 100}% confidence)`);
    }
  }
};
```

## ✅ Benefits

1. **Earlier Classification** - Happens before upload, not after
2. **Better UX** - User sees suggestion immediately upon file selection
3. **No Dataset ID Dependency** - Works with raw files
4. **Faster Feedback** - Classification happens in parallel with user reviewing other fields
5. **Reduced Server Load** - No need to store file temporarily for classification

## 🚀 Ready for Integration

The API is now properly designed to work with the file selection flow. Call it as soon as the user selects a CSV file, and the dropdown will be populated with the AI's suggestion before they even upload the dataset!

