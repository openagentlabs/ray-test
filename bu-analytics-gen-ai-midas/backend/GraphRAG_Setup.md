## 1. Knowledge Repo Updation

`KG_Creation_GraphRAG/GraphRAG_Demo.py` handles file uploads, indexing, and querying via CLI. 
!!! User can cd KG_Creation_GraphRAG
Activate virtual environment as venv/Scripts/activate
Then execute streamlit run.\GraphRAG_Demo.py 
And use the UI to simply update knowledge repo KG, updated KG is saved in my-project directory !!!

```69:384:midas/KG_Creation_GraphRAG/GraphRAG_Demo.py
PROJECT_ROOT = Path("my-project")  
```
**If this Path("my-project") is changed, the directory at which knowledge repo is created gets changed**



## 2. Setting up Knowledge Repo in MIDAS
1. Install Python 3.12.10: https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe

2. Python 3.12 interpreter (GraphRAG currently requires it): Update the paths in `backend/setup_graphrag_env.ps1` -> Run this script for creating a virtual environment for GraphRAG and installing graphrag after Python3.12.10 is installed and ready
1:24:midas/backend/setup_graphrag_env.ps1
$python312 = "C:\Users\saiyam268728\OneDrive - EXLService.com (I) Pvt. Ltd\Documents\MIDAS-Saiyam\KnowledgeRepo_To_KG\venv\Scripts\python.exe"
& $python312 -m pip install graphrag
**python312 needs to be updated with your own path**

3.`backend/app/services/graphrag_service.py` runs GraphRAG commands through `backend/graphrag_query_runner.py`, using a Python 3.12 interpreter path determined at startup.  
12:200:midas/backend/app/services/graphrag_service.py
self.graphrag_root = Path(.../"knowledge_repo_kg")
self.python_312_path = self._find_python_312()
possible_paths = [  
    r"C:\Users\saiyam268728\OneDrive - EXLService.com (I) Pvt. Ltd\Documents\MIDAS-Saiyam\KnowledgeRepo_To_KG\venv\Scripts\python.exe",
    r"C:\Python312\python.exe",
    ...
] **Update possible_paths with your own path where Python3.12.10 is installed**

4. Update Installations from requirements.txt: pip install -r requirements.txt

5. Environment Variables Updation: Update `backend/.env` as per .env.backup

6. Configuration Changes for KG_Creation/knowledge_repo: `KG_Creation_GraphRAG/my-project/settings.yaml` and in `knowledge_repo/settings.yaml`
Update the following:
- `models.default_chat_model` → `model`, `api_base`, `api_version`
**This api_base: value in settings.yaml needs to be updated with your Azure Endpoints**
- `models.default_embedding_model` → endpoint/deployment info

7. `backend/knowledge_repo_kg/` is the directory where all content of updated knowledge repo as in 'KG_Creation_GraphRAG/my-project' should be pasted, as it is folder by folder

8. **Ensure that GRAPHRAG_API_KEY is added as a variable in backend/.env and also knowledge_repo/.env the value for this variable is API KEY value of Azure OpenAI**


## 3. Verification Checklist

- `python3.12 --version` and `graphrag --help` succeed inside the venv.
- `GRAPHRAG_API_KEY` is set (`$Env:GRAPHRAG_API_KEY` on PowerShell).
- Streamlit dashboard shows non-zero counts for nodes/relationships.
- Backend logs confirm it resolved the Python 3.12 path and GraphRAG root.

- `graphrag query --root <project> --method local --query "sanity check"` returns text.

## 4. Hybrid vector-first router

- The backend now runs a `ContextRouter` before every GraphRAG query. That router uses the FAISS-backed `vector_store.search()` (documents + vectors in `midas/backend/vector_store/`) to score similarity against the user query and compute coverage metrics.  
- `ContextRouter.evaluate` returns a status (`vector_only`, `ambiguous`, or `low`) plus a concatenated `vector_context`. When the vector store is confident (`vector_only`), GraphRAG is skipped entirely and the agent receives the already-indexed excerpts. When GraphRAG is still needed, the router appends the vector context to the enhanced query so GraphRAG has the same hints that produced the vector hit.
- If GraphRAG fails, the router still falls back to those vector snippets instead of returning an empty result, so agents always get something actionable. Check `backend/app/services/graphrag_client.py` logs for `Context router outcome` lines plus the router metrics logged when a GraphRAG request uses the vector context or when the `vector_only` shortcut is taken.

## 5. Rebuilding the FAISS Vector Store after adding text files

1. Drop any new `.txt` knowledge files into `midas/backend/knowledge_repo_kg/input/`. These are the raw sources GraphRAG ingests before it compiles `knowledge_base.json` (see the streamlit UI in `KG_Creation_GraphRAG/GraphRAG_Demo.py`).
2. Re-run the GraphRAG knowledge graph exporter/CLI (`GraphRAG_Demo.py` or the `graphrag` CLI) so the updated knowledge repo is written under `midas/knowledge_base.json`. That file is what the FAISS builder consumes.
3. Restart the backend (it calls `vector_store.create_index_from_knowledge_base("knowledge_base.json")` inside `backend/app/api/routes.py::initialize_vector_store`) or hit `POST /api/v1/vector-store/reinitialize` while the service is running to rebuild the FAISS index in `midas/backend/vector_store/documents.pkl` + `faiss_index`.
4. Confirm the vector store loaded in the logs (`vector_store_loaded` entries in `backend/app/api/routes.py` and `vector_store.save_index()` log lines). Once rebuilt, the context router’s `vector_store.search()` will start returning the new snippets and the hybrid router described above will use those results before hitting GraphRAG.
