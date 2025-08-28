// components/FileUpload/FileUpload.tsx
import React, { useCallback, useState } from 'react';
import { useFileUpload } from '../../hooks/useFileUpload';
import { Button } from '../UI/Button';
import { LoadingSpinner } from '../UI/LoadingSpinner';

interface FileUploadProps {
  onUploadComplete?: () => void;
}

export const FileUpload: React.FC<FileUploadProps> = ({ onUploadComplete }) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const { uploading, uploadError, uploadResult, uploadFiles, clearUploadState } = useFileUpload();

  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    setSelectedFiles(files);
    clearUploadState();
  }, [clearUploadState]);

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0) return;

    const result = await uploadFiles(selectedFiles);
    if (result) {
      setSelectedFiles([]);
      onUploadComplete?.();
      // Clear the file input
      const fileInput = document.getElementById('file-input') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
    }
  }, [selectedFiles, uploadFiles, onUploadComplete]);

  const isSupported = (name: string) => {
    const ext = name.toLowerCase().split('.').pop() || '';
    return ['pdf','docx','xlsx','csv','txt'].includes(ext);
  };

  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const files = Array.from(event.dataTransfer.files).filter(
      file => isSupported(file.name)
    );
    setSelectedFiles(files);
    clearUploadState();
  }, [clearUploadState]);

  const handleDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
  }, []);

  return (
    <div className="border-b border-gray-700 pb-4 mb-4">
      <div
        className="border-2 border-dashed border-gray-600 rounded-lg p-6 text-center hover:border-gray-500 transition-colors"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <div className="space-y-4">
          <div>
            <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
              <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p className="text-gray-300">Upload healthcare-related documents (PDF, DOCX, XLSX, CSV, TXT)</p>
            <p className="text-sm text-gray-400">Drag and drop files here or click to browse</p>
          </div>
          
          <input
            id="file-input"
            type="file"
            multiple
            accept=".pdf,.docx,.xlsx,.csv,.txt"
            onChange={handleFileSelect}
            className="hidden"
          />
          
          <Button
            onClick={() => document.getElementById('file-input')?.click()}
            variant="secondary"
            disabled={uploading}
          >
            Choose Files
          </Button>
        </div>
      </div>

      {selectedFiles.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-medium text-gray-300 mb-2">Selected Files:</h4>
          <div className="space-y-2">
            {selectedFiles.map((file, index) => (
              <div key={index} className="flex justify-between items-center bg-gray-800 rounded p-2">
                <span className="text-sm text-gray-300">{file.name}</span>
                <span className="text-xs text-gray-400">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
              </div>
            ))}
          </div>
          
          <div className="mt-4 flex space-x-2">
            <Button
              onClick={handleUpload}
              disabled={uploading || selectedFiles.length === 0}
              className="flex items-center space-x-2"
            >
              {uploading && <LoadingSpinner size="sm" />}
              <span>{uploading ? 'Uploading...' : 'Upload Files'}</span>
            </Button>
            
            <Button
              onClick={() => {
                setSelectedFiles([]);
                clearUploadState();
              }}
              variant="secondary"
              disabled={uploading}
            >
              Clear
            </Button>
          </div>
        </div>
      )}

      {uploadError && (
        <div className="mt-4 p-3 bg-red-900/50 border border-red-700 rounded-md">
          <p className="text-red-300 text-sm">{uploadError}</p>
        </div>
      )}

      {uploadResult && (
        <div className="mt-4 p-3 bg-green-900/50 border border-green-700 rounded-md">
          <p className="text-green-300 text-sm">{uploadResult.message}</p>
          {uploadResult.rejected_files.length > 0 && (
            <div className="text-yellow-300 text-sm mt-2 space-y-1">
              <p className="font-medium">Rejected files:</p>
              <ul className="list-disc list-inside">
                {uploadResult.rejected_files.map((rf, idx) => (
                  <li key={idx}>
                    <span className="text-yellow-200">{rf.filename}</span>
                    {rf.reason && <span className="text-yellow-400"> — {rf.reason}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};