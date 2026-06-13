import { useState } from 'react';
import type { ChangeEvent } from 'react';
import { Upload, FileText } from 'lucide-react';
import { fastApiService } from '../services/fastApiService';

type UserKnowledgeScope = 'objectives' | 'data_treatment' | 'data_insights' | 'feature_engineering';
type UploadMode = 'immediate' | 'staged';

interface UserKnowledgeUploadPanelProps {
  datasetId: string | null | undefined;
  scope: UserKnowledgeScope;
  mode?: UploadMode;
  files?: File[];
  useAcrossMidas?: boolean;
  useExlExpertise?: boolean;
  onFilesChange?: (files: File[]) => void;
  onToggleChange?: (payload: { useAcrossMidas: boolean; useExlExpertise: boolean }) => void;
}

const SUPPORTED_FORMATS = ['.txt', '.csv', '.xlsx', '.pdf', '.docx'];
const USE_ACROSS_KEY = 'user_knowledge_use_across_midas';
const USE_EXL_KEY = 'user_knowledge_use_exl_expertise';

const UserKnowledgeUploadPanel: React.FC<UserKnowledgeUploadPanelProps> = ({
  datasetId,
  scope,
  mode = 'immediate',
  files,
  useAcrossMidas: useAcrossMidasProp,
  useExlExpertise: useExlExpertiseProp,
  onFilesChange,
  onToggleChange,
}) => {
  const [localFiles, setLocalFiles] = useState<File[]>([]);
  const [localUseAcrossMidas, setLocalUseAcrossMidas] = useState(() => {
    if (mode === 'staged') {
      return true;
    }
    if (typeof window === 'undefined') {
      return true;
    }
    const stored = sessionStorage.getItem(USE_ACROSS_KEY);
    return stored === null ? true : stored === 'true';
  });
  const [localUseExlExpertise, setLocalUseExlExpertise] = useState(() => {
    if (mode === 'staged') {
      return true;
    }
    if (typeof window === 'undefined') {
      return true;
    }
    const stored = sessionStorage.getItem(USE_EXL_KEY);
    return stored === null ? true : stored === 'true';
  });
  const [isUploading, setIsUploading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const resolvedDatasetId =
    datasetId || (typeof window !== 'undefined' ? sessionStorage.getItem('dataset_id') : null);
  const globalCount = typeof window !== 'undefined'
    ? Number(sessionStorage.getItem('user_knowledge_global_files_count') || 0)
    : 0;

  const resolvedFiles = files ?? localFiles;
  const useAcrossMidas = useAcrossMidasProp ?? localUseAcrossMidas;
  const useExlExpertise = useExlExpertiseProp ?? localUseExlExpertise;

  const updatePreferences = async (nextAcross: boolean, nextExl: boolean) => {
    if (!resolvedDatasetId || mode !== 'immediate') {
      return;
    }
    if (typeof window !== 'undefined') {
      sessionStorage.setItem(USE_ACROSS_KEY, String(nextAcross));
      sessionStorage.setItem(USE_EXL_KEY, String(nextExl));
    }
    try {
      await fastApiService.updateUserKnowledgePreferences({
        dataset_id: resolvedDatasetId,
        scope,
        use_across_midas: nextAcross,
        use_exl_expertise: nextExl,
      });
    } catch (error) {
      console.error('User knowledge preference update failed:', error);
    }
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files || []);
    const nextFiles = mode === 'staged' ? [...resolvedFiles, ...selected] : selected;
    if (files === undefined) {
      setLocalFiles(nextFiles);
    }
    setStatus(null);
    onFilesChange?.(nextFiles);
  };

  const handleUpload = async () => {
    if (!resolvedDatasetId) {
      setStatus('Please upload a dataset first.');
      return;
    }
    if (resolvedFiles.length === 0) {
      setStatus('Select at least one file to upload.');
      return;
    }

    setIsUploading(true);
    setStatus('Indexing your knowledge...');
    try {
      const response = await fastApiService.uploadUserKnowledge({
        dataset_id: resolvedDatasetId,
        scope,
        use_across_midas: useAcrossMidas,
        use_exl_expertise: useExlExpertise,
        files: resolvedFiles,
      });
      if (useAcrossMidas) {
        const updated = globalCount + resolvedFiles.length;
        sessionStorage.setItem('user_knowledge_global_files_count', String(updated));
      }
      const warnings = response?.warnings?.length ? ` Warnings: ${response.warnings.join('; ')}` : '';
      setStatus(`Knowledge ready (${response.indexed_chunks} chunks).${warnings}`);
      if (mode === 'immediate') {
        if (files === undefined) {
          setLocalFiles([]);
        }
        onFilesChange?.([]);
      }
    } catch (error: any) {
      setStatus(error?.message || 'Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-6 space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Add your own Business Standards & Knowledge
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">We don't see or store your business knowledge!</p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center px-3 py-2 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-lg cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/50 border border-blue-200 dark:border-blue-700">
            <Upload className="h-4 w-4 mr-2" />
            <span>Upload files</span>
            <input
              type="file"
              className="hidden"
              multiple
              accept={SUPPORTED_FORMATS.join(',')}
              onChange={handleFileChange}
            />
          </label>
          <span className="text-xs text-gray-500 dark:text-gray-400">Supported: {SUPPORTED_FORMATS.join(', ')}</span>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {mode === 'immediate' && (
            <button
              onClick={handleUpload}
              disabled={isUploading}
              className="px-3 py-2 bg-blue-600 dark:bg-blue-500 text-white rounded-lg hover:bg-blue-700 dark:hover:bg-blue-600 disabled:opacity-50"
            >
              {isUploading ? 'Indexing...' : 'Upload & Index'}
            </button>
          )}

          <div className="flex items-center space-x-2 text-sm text-gray-700 dark:text-gray-300">
            <button
              type="button"
              onClick={() => {
                const next = !useAcrossMidas;
                if (useAcrossMidasProp === undefined) {
                  setLocalUseAcrossMidas(next);
                }
                onToggleChange?.({ useAcrossMidas: next, useExlExpertise });
                if (mode === 'immediate') {
                  updatePreferences(next, useExlExpertise);
                }
              }}
              className={`relative inline-flex h-4 w-8 items-center rounded-full transition-colors ${
                useAcrossMidas ? 'bg-green-500' : 'bg-red-500'
              }`}
            >
              <span
                className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                  useAcrossMidas ? 'translate-x-4' : 'translate-x-1'
                }`}
              />
            </button>
            <span>Use across EXLdecision.ai</span>
          </div>

          <div className="flex items-center space-x-2 text-sm text-gray-700 dark:text-gray-300">
            <button
              type="button"
              onClick={() => {
                const next = !useExlExpertise;
                if (useExlExpertiseProp === undefined) {
                  setLocalUseExlExpertise(next);
                }
                onToggleChange?.({ useAcrossMidas, useExlExpertise: next });
                if (mode === 'immediate') {
                  updatePreferences(useAcrossMidas, next);
                }
              }}
              className={`relative inline-flex h-4 w-8 items-center rounded-full transition-colors ${
                useExlExpertise ? 'bg-green-500' : 'bg-red-500'
              }`}
            >
              <span
                className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                  useExlExpertise ? 'translate-x-4' : 'translate-x-1'
                }`}
              />
            </button>
            <span>Use EXL's Expertise</span>
          </div>
        </div>
      </div>

      {resolvedFiles.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center space-x-2 text-sm text-gray-700 dark:text-gray-300">
            <FileText className="h-4 w-4" />
            <span>{resolvedFiles.length} file(s) selected</span>
          </div>
        </div>
      )}

      {useAcrossMidas && globalCount > 0 && (
        <div className="text-xs text-gray-600 dark:text-gray-400">Global knowledge files available: {globalCount}</div>
      )}

      {status && <div className="text-sm text-gray-700 dark:text-gray-300">{status}</div>}
    </div>
  );
};

export default UserKnowledgeUploadPanel;
