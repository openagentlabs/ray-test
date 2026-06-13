# View Codebook Feature Documentation

## Overview
This feature adds a "View Codebook" button to the Global Supervised Model Training panel that allows users to view the backend implementation code for each machine learning algorithm (Random Forest, Gradient Boosting, Logistic Regression).

## Changes Made

### 1. Backend - Codebook Storage (`/backend/app/notebooks/`)
Created JSON files containing code implementations for each algorithm:
- `random_forest.json` - Random Forest implementation details
- `gradient_boosting.json` - Gradient Boosting implementation details  
- `logistic_regression.json` - Logistic Regression implementation details

Each codebook contains:
- Algorithm title and description
- Step-by-step code sections covering:
  1. Importing libraries
  2. Loading and preparing data
  3. Problem type detection
  4. Data splitting (train/val/test)
  5. Data preprocessing
  6. Model initialization
  7. K-fold cross-validation
  8. Training final model
  9. Test set evaluation
  10. Feature importance/coefficients analysis

### 2. Backend - API Schema Updates (`/backend/app/models/schemas.py`)
Added new schemas:
```python
class CodebookSection(BaseModel):
    title: str
    type: str
    content: str

class ModelCodebookResponse(BaseModel):
    success: bool
    algorithm: str
    title: str
    description: str
    sections: List[CodebookSection]
```

### 3. Backend - New API Endpoint (`/backend/app/api/routes.py`)
Added endpoint to serve codebook data:
```python
@chat_router.get("/model-codebook/{algorithm}", response_model=ModelCodebookResponse)
async def get_model_codebook(algorithm: str, current_user = Depends(get_current_user_dependency))
```

Endpoint:
- **Method**: GET
- **Path**: `/chat/model-codebook/{algorithm}`
- **Parameters**: `algorithm` (random_forest | gradient_boosting | logistic_regression)
- **Returns**: JSON containing codebook sections

### 4. Frontend - Service Layer (`/frontend/src/services/fastApiService.ts`)
Added TypeScript interfaces and service method:
```typescript
export interface CodebookSection {
  title: string;
  type: string;
  content: string;
}

export interface ModelCodebookResponse {
  success: boolean;
  algorithm: string;
  title: string;
  description: string;
  sections: CodebookSection[];
}

async getModelCodebook(algorithm: 'random_forest' | 'gradient_boosting' | 'logistic_regression'): Promise<ModelCodebookResponse>
```

### 5. Frontend - UI Component (`/frontend/src/components/steps/Step3_5SegmentationAgentAnalysis.tsx`)

#### Added:
1. **"View Codebook" Button**
   - Located next to "Global Supervised Model Training" heading
   - Styled with indigo/purple theme
   - Disabled when no model is selected
   - Shows loading spinner while fetching

2. **Codebook Modal**
   - Full-screen overlay with centered modal
   - Gradient header (indigo to purple)
   - Scrollable content area
   - Code sections displayed with:
     - Numbered section headers
     - Dark code blocks with syntax-friendly styling
     - Monospace font for code readability
   - Close button in header and footer

#### Key Features:
- **No changes to existing UI**: Button added without modifying the main panel layout
- **Responsive design**: Modal scales to fit screen (max 90vh)
- **Clean code presentation**: Dark theme code blocks for better readability
- **Error handling**: Alerts user if codebook fails to load
- **Loading states**: Shows spinner during fetch operation

## User Flow

1. User navigates to Step 3.5 (Global Supervised Model Training)
2. User selects a machine learning algorithm (Random Forest, Gradient Boosting, or Logistic Regression)
3. User clicks "View Codebook" button
4. System fetches the codebook from backend
5. Modal opens displaying the implementation code in sections
6. User can scroll through all code sections
7. User closes modal when done

## Technical Notes

### No Cyclical Dependencies
- All imports are properly scoped
- Service layer cleanly separates API calls from components
- No circular references between modules

### UI Consistency
- Matches existing color scheme (purple/indigo theme)
- Uses consistent spacing and typography
- Follows existing component patterns
- Button placement doesn't disrupt existing layout

### Code Quality
- TypeScript type safety throughout
- Proper error handling and loading states
- Clean separation of concerns
- Well-documented code sections

## Testing Checklist

- [x] Backend codebook files created
- [x] Backend endpoint implemented and integrated
- [x] Frontend service method added
- [x] UI component with button and modal added
- [x] No linter errors (only expected import warnings)
- [x] No cyclical dependencies
- [x] No changes to existing UI layout

## Files Modified/Created

### Created:
1. `midas/backend/app/notebooks/random_forest.json`
2. `midas/backend/app/notebooks/gradient_boosting.json`
3. `midas/backend/app/notebooks/logistic_regression.json`
4. `midas/CODEBOOK_FEATURE_README.md` (this file)

### Modified:
1. `midas/backend/app/models/schemas.py` - Added codebook schemas
2. `midas/backend/app/api/routes.py` - Added codebook endpoint and imports
3. `midas/frontend/src/services/fastApiService.ts` - Added interfaces and service method
4. `midas/frontend/src/components/steps/Step3_5SegmentationAgentAnalysis.tsx` - Added button and modal

## Future Enhancements (Optional)

1. Add syntax highlighting to code blocks
2. Add copy-to-clipboard functionality for code sections
3. Add download codebook as PDF/notebook file
4. Add search functionality within codebook
5. Add links to documentation for each algorithm

