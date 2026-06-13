# Codebook Download Feature

## Overview
Added a download button to the codebook modal that allows users to download the displayed code as a Python (.py) file for both Global Model Training and Segmentation Analysis codebooks.

## Changes Made

### 1. Frontend Component Updates

**File:** `midas/frontend/src/components/steps/Step3_5SegmentationAgentAnalysis.tsx`

#### Added Import:
```typescript
import { Brain, ChevronDown, Check, BookOpen, X, Download } from 'lucide-react';
```
- Added `Download` icon from lucide-react

#### New Handler Function:
```typescript
const handleDownloadCodebook = () => {
  if (!codebookData) return;

  // Generate Python file content
  let pythonContent = `# ${codebookData.title}\n`;
  pythonContent += `# ${codebookData.description}\n\n`;
  
  codebookData.sections.forEach((section) => {
    pythonContent += `# ${'='.repeat(80)}\n`;
    pythonContent += `# ${section.title}\n`;
    pythonContent += `# ${'='.repeat(80)}\n\n`;
    pythonContent += `${section.content}\n\n\n`;
  });

  // Create blob and download
  const blob = new Blob([pythonContent], { type: 'text/plain' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  
  // Generate filename based on type
  const timestamp = new Date().toISOString().slice(0, 10);
  const filename = codebookType === 'model' 
    ? `${codebookData.algorithm}_model_codebook_${timestamp}.py`
    : `${codebookData.algorithm}_segmentation_codebook_${timestamp}.py`;
  
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};
```

#### Updated Modal Footer:
```typescript
<div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex justify-between items-center">
  <button
    onClick={handleDownloadCodebook}
    className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
    type="button"
  >
    <Download className="h-4 w-4" />
    Download as Python File
  </button>
  <button
    onClick={() => setIsCodebookOpen(false)}
    className="px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
    type="button"
  >
    Close
  </button>
</div>
```

## Features

### Download Functionality

**File Format:** Python (.py) file  
**File Structure:**
```python
# [Title]
# [Description]

# ================================================================================
# [Section 1 Title]
# ================================================================================

[Section 1 Code]


# ================================================================================
# [Section 2 Title]
# ================================================================================

[Section 2 Code]

...
```

### File Naming Convention

The downloaded files follow a clear naming pattern:

**For Global Model Codebooks:**
```
{algorithm}_model_codebook_{date}.py
```
Examples:
- `random_forest_model_codebook_2025-10-01.py`
- `gradient_boosting_model_codebook_2025-10-01.py`
- `logistic_regression_model_codebook_2025-10-01.py`

**For Segmentation Codebooks:**
```
{algorithm}_segmentation_codebook_{date}.py
```
Examples:
- `cart_segmentation_codebook_2025-10-01.py`
- `chaid_segmentation_codebook_2025-10-01.py`

### User Experience

1. **User opens codebook modal** (either for global model or segmentation)
2. **User reviews the code** in the modal
3. **User clicks "Download as Python File"** button in the bottom-left of the modal
4. **Browser downloads the file** with the appropriate name
5. **User can run the code** independently in their Python environment

## Visual Layout

### Modal Footer - Before:
```
┌──────────────────────────────────────┐
│                                      │
│         [Close]                      │
│                                      │
└──────────────────────────────────────┘
```

### Modal Footer - After:
```
┌──────────────────────────────────────┐
│                                      │
│  [📥 Download as Python File] [Close]│
│    ↑ Green button                   │
└──────────────────────────────────────┘
```

## Technical Implementation Details

### Blob Creation
- Uses `Blob` API to create a file from text content
- MIME type: `text/plain` (Python files are plain text)
- Creates temporary object URL for download

### File Download Trigger
- Programmatically creates an `<a>` element
- Sets the `download` attribute with the filename
- Triggers click event to initiate download
- Cleans up: removes element and revokes object URL

### Timestamp Format
- Uses ISO format: `YYYY-MM-DD`
- Example: `2025-10-01`
- Extracted from `new Date().toISOString().slice(0, 10)`

### Code Formatting
- Sections separated by comment dividers (80 '=' characters)
- Clear section headers
- Preserves all original code formatting
- Includes title and description as comments at the top

## Benefits

✅ **Portability**: Users can save and share the exact code being run  
✅ **Reproducibility**: Downloaded code can be executed independently  
✅ **Documentation**: Serves as reference implementation  
✅ **Learning**: Users can study code offline in their preferred editor  
✅ **Version Control**: Timestamped files help track different configurations  
✅ **No Dependencies**: Pure client-side download, no server request needed  

## Browser Compatibility

Works in all modern browsers that support:
- Blob API ✅
- Object URLs ✅
- Download attribute on anchor tags ✅

Supported browsers:
- ✅ Chrome 14+
- ✅ Firefox 20+
- ✅ Safari 10.1+
- ✅ Edge 13+

## Example Downloaded File

**Filename:** `random_forest_model_codebook_2025-10-01.py`

**Content:**
```python
# Random Forest Classifier with K-Fold Cross-Validation
# This codebook demonstrates the backend code used to train and evaluate a Random Forest model...

# ================================================================================
# 1. Import Required Libraries
# ================================================================================

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
...

# ================================================================================
# 2. Load and Prepare Dataset
# ================================================================================

# Load your dataset
df = pd.read_csv('customer_data.csv')
...
```

## Files Modified

### Modified:
1. **midas/frontend/src/components/steps/Step3_5SegmentationAgentAnalysis.tsx**
   - Line 2: Added `Download` import
   - Lines 207-238: Added `handleDownloadCodebook` function
   - Lines 858-874: Updated modal footer with download button

### Created:
1. **midas/CODEBOOK_DOWNLOAD_FEATURE.md** (this file)

## Usage Instructions

### For Users:
1. Click "View Codebook" button (either in Global Model or Segmentation section)
2. Review the code in the modal
3. Click "Download as Python File" button at bottom-left
4. File will download to your default downloads folder
5. Open the `.py` file in any text editor or Python IDE
6. Run the code (ensure you have required libraries installed)

### For Developers:
The download function is self-contained and requires no backend changes. It:
- Formats the existing `codebookData` into Python comments and code
- Generates appropriate filename based on `codebookType` and `algorithm`
- Uses browser's native download functionality
- Cleans up resources after download

## Testing Checklist

- [x] Download button appears in modal footer
- [x] Button has correct styling (green background, white text)
- [x] Download icon appears next to text
- [x] Clicking button triggers download
- [x] Global model codebooks download with correct filename
- [x] Segmentation codebooks download with correct filename
- [x] Filename includes correct algorithm name
- [x] Filename includes current date
- [x] Downloaded file has correct structure
- [x] Downloaded file includes all sections
- [x] Code formatting is preserved
- [x] No linter errors
- [x] No runtime errors
- [x] Works for all model types (RF, GB, LR)
- [x] Works for all segmentation types (CART, CHAID)

## Future Enhancements

Potential improvements for future versions:
1. **Jupyter Notebook Export**: Export as `.ipynb` format
2. **PDF Export**: Generate styled PDF documentation
3. **Copy All Button**: One-click copy all code to clipboard
4. **Custom Filename**: Let users specify filename before download
5. **Include Context**: Add dataset info, selected variables as comments
6. **Multiple Formats**: Dropdown to choose between .py, .ipynb, .pdf

## Consistency

This feature maintains consistency across:
- ✅ Both Global Model and Segmentation codebooks
- ✅ All model algorithms (Random Forest, Gradient Boosting, Logistic Regression)
- ✅ All segmentation methods (CART, CHAID)
- ✅ Same download behavior for all codebook types
- ✅ Consistent naming convention
- ✅ Uniform file structure

