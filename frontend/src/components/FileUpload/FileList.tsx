// components/FileUpload/FileList.tsx
import React from 'react';
import { Button } from '../UI/Button';
import { LoadingSpinner } from '../UI/LoadingSpinner';
import { FileListResponse } from '../../types';

type Props = {
  files: FileListResponse | null;
  loading: boolean;
  error: string | null;
  onDelete: (filename: string) => void;
  onClearAll: () => void;
};

export const FileList: React.FC<Props> = ({ files, loading, error, onDelete, onClearAll }) => {
  if (loading && !files) {
    return (
      <div className="flex items-center justify-center p-4">
        <LoadingSpinner />
        <span className="ml-2 text-gray-300">Loading files...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-900/50 border border-red-700 rounded-md">
        <p className="text-red-300 text-sm">{error}</p>
      </div>
    );
  }

  if (!files || files.total_files === 0) {
    return (
      <div className="text-center p-4 text-gray-400">
        <p>No files uploaded yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-white">
          Uploaded Files ({files.total_files})
        </h3>
        {files.total_files > 0 && (
          <Button
            onClick={onClearAll}
            variant="danger"
            size="sm"
            disabled={loading}
          >
            Clear All
          </Button>
        )}
      </div>

      <div className="bg-gray-800 rounded-lg p-4 mb-4">
        <p className="text-sm text-gray-300">
          Total chunks: {files.total_chunks}
        </p>
      </div>

      <div className="space-y-2">
        {files.file_details.map((file) => (
          <div key={file.filename} className="bg-gray-800 rounded-lg p-4">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <h4 className="font-medium text-white">{file.filename}</h4>
                <p className="text-sm text-gray-400 mt-1">
                  {file.chunk_count} chunks
                </p>
                {file.sample_text && (
                  <p className="text-xs text-gray-500 mt-2 italic">
                    {file.sample_text}
                  </p>
                )}
              </div>
              <Button
                onClick={() => onDelete(file.filename)}
                variant="danger"
                size="sm"
                disabled={loading}
                className="ml-4"
              >
                {loading ? <LoadingSpinner size="sm" /> : 'Delete'}
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};