# Quick Start Guide - Model Documentation Feature

## For Users

### How to Use the Model Documentation Feature

1. **Navigate to Model Documentation Page** (Step 9 in Model Builder)

2. **Click "Generate Documentation"**
   - The system will collect all data from your modeling journey
   - It will generate a data summary using AI
   - An interactive report will appear

3. **Review and Edit the Documentation**
   - Hover over any text field to see a pencil icon
   - Click the pencil to edit
   - Make your changes
   - Click "Save" to keep changes or "Cancel" to discard

4. **Download Your Documentation**
   - Scroll to the bottom of the report
   - Click "Download Documentation (.docx)"
   - Your documentation will be saved as a Word document

### What Gets Included in the Documentation

#### OBJECTIVE Section (Currently Implemented)
- **Model Objective**
  - Description: From your project description (if provided)
  - Problem Statement: From Step 1 - Objectives & Data
- **Data Summary**
  - AI-generated 5-line summary of your dataset
  - Based on your columns, data dictionary, and objectives

### Tips
- Fill in the Problem Statement in Step 1 for better documentation
- Upload a data dictionary for more accurate summaries
- Edit any generated content to match your specific needs
- The documentation persists during your session but is cleared when you close the browser

## For Developers

### Installation

1. **Install Backend Dependencies**
```bash
cd midas/backend
pip install -r requirements.txt
```

2. **Verify python-docx is installed**
```bash
pip list | grep python-docx
```

### Running the Application

1. **Start Backend**
```bash
cd midas/backend
python run_server.py
```

2. **Start Frontend**
```bash
cd midas/frontend
npm run dev
```

### API Endpoints

#### Generate Data Summary
```
POST /api/v1/documentation/generate-data-summary
Content-Type: application/json

{
  "columns": ["col1", "col2", ...],
  "data_dictionary": "optional data dictionary content",
  "model_objective": "optional objective description"
}

Response:
{
  "success": true,
  "summary": "Generated 5-line summary..."
}
```

#### Download Documentation
```
POST /api/v1/documentation/download
Content-Type: application/json

{
  "objectives": {
    "modelObjective": {
      "description": "...",
      "problemStatement": "..."
    },
    "dataSummary": {
      "content": "...",
      "metadata": {...}
    }
  },
  "meta": {...}
}

Response: Binary .docx file
```

### State Management

The documentation state is managed by `DocumentationContext`:

```typescript
import { useDocumentation } from '../contexts/DocumentationContext';

const { 
  documentationData,
  updateModelObjective,
  updateDataSummary,
  generateDocumentation,
  isDocumentationGenerated 
} = useDocumentation();

// Update model objective
updateModelObjective({ 
  description: "...",
  problemStatement: "..." 
});

// Update data summary
updateDataSummary({ 
  content: "...",
  metadata: {...}
});

// Mark as generated
generateDocumentation();
```

### Adding New Documentation Sections

1. **Update DocumentationContext Interface**
```typescript
export interface DocumentationData {
  objectives: {...},
  // Add your new section
  newSection: {
    field1: string;
    field2: number;
  };
}
```

2. **Add Update Methods**
```typescript
const updateNewSection = (data: Partial<DocumentationData['newSection']>) => {
  setDocumentationData(prev => ({
    ...prev,
    newSection: {
      ...prev.newSection,
      ...data,
    },
  }));
};
```

3. **Update DocumentationViewer**
```typescript
// Add new section rendering
<div className="space-y-4">
  <div className="bg-blue-100 rounded-lg px-4 py-3 border border-blue-200">
    <h3 className="text-xl font-semibold text-gray-900">
      <span className="mr-2">2.</span>
      NEW SECTION
    </h3>
  </div>
  {/* Add your fields */}
</div>
```

4. **Sync Data from Source Components**
```typescript
// In your source component
import { useDocumentation } from '../contexts/DocumentationContext';

const { updateNewSection } = useDocumentation();

// When data changes
updateNewSection({ field1: "value" });
```

5. **Update .docx Generation**
```python
# In documentation_routes.py
new_section = documentation_data.get('newSection', {})
doc.add_heading('2. NEW SECTION', 1)
doc.add_paragraph(new_section.get('field1', 'Not provided'))
```

### Debugging

#### Check SessionStorage
```javascript
// In browser console
console.log(sessionStorage.getItem('model_documentation_data'));
console.log(sessionStorage.getItem('model_documentation_generated'));
```

#### Check Backend Logs
```bash
tail -f midas/backend/logs/midas.log
```

#### Common Issues

1. **Documentation not generating**
   - Check if dataset_config exists in sessionStorage
   - Verify LLM service is configured
   - Check backend logs for errors

2. **Download not working**
   - Verify python-docx is installed
   - Check CORS settings
   - Verify blob creation in browser console

3. **Edits not saving**
   - Check DocumentationContext is properly imported
   - Verify sessionStorage is accessible
   - Check browser console for errors

### Testing

```bash
# Frontend tests
cd midas/frontend
npm test

# Backend tests
cd midas/backend
pytest
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Step 9: Model Documentation                      │  │
│  │  - Generate Documentation Button                  │  │
│  │  - Documentation Viewer (Editable)                │  │
│  │  - Download Button                                │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              DocumentationContext                        │
│  - Session-based state management                       │
│  - Stores all documentation data                        │
│  - Syncs with sessionStorage                            │
│  - Provides update methods                              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Source Components                           │
│  - Step1ObjectivesData (Problem Statement)              │
│  - Step2DataQC (Quality metrics)                        │
│  - Step4FeatureEngineering (Transformations)            │
│  - Step7ModelTraining (Training results)                │
│  - Step8AIExplainability (Explanations)                 │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Backend API                                 │
│  POST /documentation/generate-data-summary              │
│  POST /documentation/download                           │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              LLM Service                                 │
│  - Generate text summaries                              │
│  - Azure OpenAI integration                             │
└─────────────────────────────────────────────────────────┘
```

## Next Steps

### Immediate Tasks
1. Install python-docx: `pip install python-docx`
2. Restart backend server
3. Test documentation generation
4. Test download functionality

### Future Enhancements
- Add more documentation sections
- Include charts and images
- Add PDF export
- Implement version history
- Add collaboration features

## Support

For issues or questions:
1. Check the logs: `midas/backend/logs/midas.log`
2. Review the implementation summary: `midas/DOCUMENTATION_FEATURE_SUMMARY.md`
3. Check browser console for frontend errors
4. Verify all dependencies are installed

