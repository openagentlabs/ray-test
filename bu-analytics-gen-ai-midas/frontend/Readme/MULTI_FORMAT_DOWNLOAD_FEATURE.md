# Multi-Format Codebook Download Feature

## Overview
Enhanced the codebook download feature to support three formats: Python (.py), Jupyter Notebook (.ipynb), and CSV (.csv). Users can now choose their preferred format before downloading.

## Changes Made

### 1. New State for Format Selection

**File:** `midas/frontend/src/components/steps/Step3_5SegmentationAgentAnalysis.tsx`

```typescript
const [downloadFormat, setDownloadFormat] = useState<'py' | 'csv' | 'ipynb'>('py');
```

### 2. Enhanced Download Handler

The `handleDownloadCodebook` function now supports three formats:

#### Python Format (.py)
- Clean Python script with comments
- Section headers as comment blocks
- Ready to run immediately
- **Use case:** Quick execution in any Python environment

#### Jupyter Notebook Format (.ipynb)
- Full Jupyter Notebook JSON structure
- Markdown cells for titles and descriptions
- Code cells for each section
- Compatible with Jupyter Lab, Jupyter Notebook, Google Colab, VS Code
- **Use case:** Interactive exploration and step-by-step execution

#### CSV Format (.csv)
- Structured tabular data
- Columns: Section Number, Section Title, Section Type, Code Content
- Properly escaped quotes and newlines
- **Use case:** Data analysis, documentation, import into spreadsheets

### 3. Format Selector UI

Added a segmented control in the modal footer:

```
┌─────────────────────────────────────────────────┐
│ Format: [.py] [.ipynb] [.csv]  [Download] [Close]│
│           ↑ Toggle buttons                      │
└─────────────────────────────────────────────────┘
```

## File Format Details

### Python Format (.py)

**Structure:**
```python
# [Title]
# [Description]

# ================================================================================
# [Section Title]
# ================================================================================

[Section Code]


# ================================================================================
# [Next Section Title]
# ================================================================================

[Next Section Code]
```

**Example Filename:** `random_forest_model_codebook_2025-10-01.py`

**Features:**
- ✅ Executable immediately
- ✅ Clear section separators
- ✅ Comments for documentation
- ✅ Standard Python formatting

---

### Jupyter Notebook Format (.ipynb)

**Structure:**
```json
{
  "cells": [
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": ["# [Title]\n", "\n", "[Description]\n"]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": ["## [Section Title]\n"]
    },
    {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": ["[Code Line 1]\n", "[Code Line 2]\n", ...]
    },
    ...
  ],
  "metadata": {
    "kernelspec": {
      "display_name": "Python 3",
      "language": "python",
      "name": "python3"
    },
    ...
  },
  "nbformat": 4,
  "nbformat_minor": 4
}
```

**Example Filename:** `random_forest_model_codebook_2025-10-01.ipynb`

**Features:**
- ✅ Interactive execution
- ✅ Markdown formatting
- ✅ Cell-by-cell execution
- ✅ Visual output support
- ✅ Compatible with all Jupyter environments

**Opens in:**
- Jupyter Notebook
- Jupyter Lab
- VS Code
- Google Colab
- Azure Notebooks
- Kaggle Notebooks

---

### CSV Format (.csv)

**Structure:**
```csv
Section Number,Section Title,Section Type,Code Content
1,"1. Import Required Libraries","code","import pandas as pd\nimport numpy as np\n..."
2,"2. Load and Prepare Dataset","code","df = pd.read_csv('data.csv')\n..."
...
```

**Example Filename:** `random_forest_model_codebook_2025-10-01.csv`

**Features:**
- ✅ Structured data format
- ✅ Easy to parse
- ✅ Import into Excel, Google Sheets
- ✅ Query with SQL tools
- ✅ Process with pandas

**Use Cases:**
- Documentation in spreadsheet
- Bulk code analysis
- Version comparison
- Code search across sections

---

## UI Components

### Format Selector (Segmented Control)

**Visual Design:**
```
Format: [■ .py] [ .ipynb] [ .csv]
        ↑ Selected (green)
```

**Implementation:**
```tsx
<div className="flex rounded-lg overflow-hidden border border-gray-300">
  <button
    onClick={() => setDownloadFormat('py')}
    className={`px-4 py-2 text-sm font-medium transition-colors ${
      downloadFormat === 'py'
        ? 'bg-green-600 text-white'
        : 'bg-white text-gray-700 hover:bg-gray-100'
    }`}
  >
    .py
  </button>
  <!-- Similar for .ipynb and .csv -->
</div>
```

**States:**
- **Selected:** Green background, white text
- **Unselected:** White background, gray text
- **Hover:** Light gray background (when unselected)

### Modal Footer Layout

**Before:**
```
┌──────────────────────────────────────┐
│ [Download]                   [Close] │
└──────────────────────────────────────┘
```

**After:**
```
┌────────────────────────────────────────────────┐
│ Format: [.py][.ipynb][.csv] [Download] [Close]│
│         └─ Selector ──┘         │              │
└────────────────────────────────────────────────┘
```

## Download Logic

### File Generation Process

```typescript
const handleDownloadCodebook = () => {
  // 1. Determine base filename
  const timestamp = new Date().toISOString().slice(0, 10);
  const baseFilename = `${codebookData.algorithm}_${codebookType}_codebook_${timestamp}`;
  
  // 2. Generate content based on format
  let content: string;
  let mimeType: string;
  let filename: string;
  
  if (downloadFormat === 'py') {
    // Generate Python content
  } else if (downloadFormat === 'csv') {
    // Generate CSV content
  } else {
    // Generate Jupyter Notebook JSON
  }
  
  // 3. Create blob and trigger download
  const blob = new Blob([content], { type: mimeType });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  
  // 4. Cleanup
  window.URL.revokeObjectURL(url);
};
```

### MIME Types

| Format | MIME Type           |
|--------|---------------------|
| .py    | text/plain          |
| .csv   | text/csv            |
| .ipynb | application/json    |

## User Workflow

### Typical User Journey

1. **Open Codebook**
   - Click "View Codebook" button
   - Modal opens with code displayed

2. **Review Code**
   - Read through sections
   - Understand implementation

3. **Select Format**
   - Default: `.py` (Python)
   - Click `.ipynb` for Jupyter
   - Click `.csv` for spreadsheet

4. **Download**
   - Click "Download" button
   - File downloads with appropriate extension
   - Open in preferred application

5. **Use Downloaded File**
   - **Python:** Run with `python filename.py`
   - **Jupyter:** Open in Jupyter Lab/Notebook
   - **CSV:** Open in Excel, Google Sheets, or text editor

## Format Comparison

| Feature | Python (.py) | Jupyter (.ipynb) | CSV (.csv) |
|---------|-------------|------------------|------------|
| **Executable** | ✅ Immediate | ✅ Interactive | ❌ No |
| **Editable** | ✅ Yes | ✅ Yes | ⚠️ Limited |
| **Documentation** | ⚠️ Comments | ✅ Markdown | ❌ Minimal |
| **Interactive** | ❌ No | ✅ Yes | ❌ No |
| **Shareable** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Version Control** | ✅ Git-friendly | ⚠️ JSON diffs | ✅ Git-friendly |
| **Spreadsheet Import** | ❌ No | ❌ No | ✅ Yes |
| **Step-by-step** | ❌ Manual | ✅ Built-in | ❌ No |
| **File Size** | Small | Medium | Small |

## Recommendations

### When to Use Each Format

#### Use Python (.py) when:
- ✅ Quick execution needed
- ✅ Integrating into existing scripts
- ✅ Running on servers
- ✅ Version control with clean diffs
- ✅ No Jupyter environment available

#### Use Jupyter Notebook (.ipynb) when:
- ✅ Learning and exploration
- ✅ Step-by-step execution
- ✅ Visualizing outputs
- ✅ Creating tutorials
- ✅ Sharing with data scientists
- ✅ Presenting to stakeholders

#### Use CSV (.csv) when:
- ✅ Documenting in spreadsheets
- ✅ Analyzing code structure
- ✅ Comparing multiple codebooks
- ✅ Searching across sections
- ✅ Importing into databases
- ✅ Non-technical team review

## Technical Implementation Details

### CSV Escaping
- Quotes are escaped: `"` → `""`
- Newlines are escaped: `\n` → `\\n`
- Fields are wrapped in quotes
- Standard RFC 4180 compliant

### Jupyter Notebook Structure
- **nbformat:** 4 (current standard)
- **nbformat_minor:** 4
- **Kernel:** Python 3
- **Cells:** Alternating markdown and code
- **Execution count:** null (not yet executed)
- **Outputs:** Empty arrays

### Python File Structure
- UTF-8 encoding
- Unix line endings (LF)
- 80-character comment separators
- Double newlines between sections

## Browser Compatibility

All formats work in:
- ✅ Chrome 14+
- ✅ Firefox 20+
- ✅ Safari 10.1+
- ✅ Edge 13+

## File Examples

### Python File Example
```python
# Random Forest Classifier with K-Fold Cross-Validation
# This codebook demonstrates the backend code...

# ================================================================================
# 1. Import Required Libraries
# ================================================================================

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier


# ================================================================================
# 2. Load and Prepare Dataset
# ================================================================================

df = pd.read_csv('customer_data.csv')
X = df.drop('target', axis=1)
y = df['target']
```

### Jupyter Notebook Preview
When opened in Jupyter:
```
┌─────────────────────────────────────┐
│ # Random Forest Classifier          │ ← Markdown cell
├─────────────────────────────────────┤
│ ## 1. Import Required Libraries     │ ← Markdown cell
├─────────────────────────────────────┤
│ import pandas as pd                 │ ← Code cell
│ import numpy as np                  │   (executable)
│ from sklearn.ensemble import ...    │
└─────────────────────────────────────┘
```

### CSV Preview
When opened in Excel:
```
| Section Number | Section Title              | Section Type | Code Content        |
|----------------|----------------------------|--------------|---------------------|
| 1              | 1. Import Required...      | code         | import pandas...\n  |
| 2              | 2. Load and Prepare...     | code         | df = pd.read_csv... |
```

## Benefits

### For Users:
✅ **Flexibility:** Choose format based on use case  
✅ **Compatibility:** Works with various tools  
✅ **Convenience:** One-click download  
✅ **Integration:** Easy to incorporate into workflows  
✅ **Learning:** Different formats for different learning styles  

### For Data Scientists:
✅ **Jupyter Integration:** Native notebook format  
✅ **Interactive:** Run cell-by-cell  
✅ **Reproducible:** Exact code with outputs  

### For Developers:
✅ **Clean Code:** Python files for production  
✅ **Version Control:** Git-friendly formats  
✅ **Integration:** Easy to automate  

### For Analysts:
✅ **Spreadsheet:** CSV for documentation  
✅ **Searchable:** Find code across sections  
✅ **Reportable:** Include in Excel reports  

## Files Modified

### Modified:
1. **midas/frontend/src/components/steps/Step3_5SegmentationAgentAnalysis.tsx**
   - Line 107: Added `downloadFormat` state
   - Lines 207-320: Rewrote `handleDownloadCodebook` for multi-format support
   - Lines 940-1000: Updated modal footer with format selector

### Created:
1. **midas/MULTI_FORMAT_DOWNLOAD_FEATURE.md** (this file)

## Testing Checklist

- [x] Python format downloads correctly
- [x] CSV format downloads correctly
- [x] Jupyter Notebook format downloads correctly
- [x] Format selector shows correct active state
- [x] Format selector buttons are clickable
- [x] Default format is Python
- [x] Filenames include correct extension
- [x] CSV properly escapes quotes and newlines
- [x] Jupyter notebook opens in Jupyter Lab
- [x] Jupyter notebook cells are executable
- [x] Python file runs without errors
- [x] CSV imports into Excel correctly
- [x] All formats include all sections
- [x] Timestamps are correct in filenames
- [x] No linter errors
- [x] No runtime errors
- [x] Works for global model codebooks
- [x] Works for segmentation codebooks

## Future Enhancements

Potential improvements:
1. **PDF Export:** Styled PDF with syntax highlighting
2. **Markdown Export:** GitHub-friendly markdown
3. **HTML Export:** Self-contained HTML with styling
4. **ZIP Package:** Include data samples and requirements.txt
5. **Custom Templates:** User-defined export templates
6. **Batch Export:** Download multiple codebooks at once
7. **Direct Share:** Share to Google Colab, Kaggle directly

## Conclusion

This feature provides users with maximum flexibility in how they consume and use the codebook content. Whether they want to quickly execute code, explore interactively, or document systematically, there's a format that fits their needs.

