// hooks/useFileUpload.ts
import { useState } from 'react';
import { apiClient, ApiError } from '../utils/api';
import { FileUploadResponse } from '../types';

export const useFileUpload = () => {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<FileUploadResponse | null>(null);

  const uploadFiles = async (files: File[]): Promise<FileUploadResponse | null> => {
    setUploading(true);
    setUploadError(null);
    setUploadResult(null);

    try {
      const result = await apiClient.uploadFiles(files);
      setUploadResult(result);
      return result;
    } catch (err) {
      const errorMessage = err instanceof ApiError ? err.message : 'Failed to upload files';
      setUploadError(errorMessage);
      return null;
    } finally {
      setUploading(false);
    }
  };

  const clearUploadState = () => {
    setUploadError(null);
    setUploadResult(null);
  };

  return {
    uploading,
    uploadError,
    uploadResult,
    uploadFiles,
    clearUploadState,
  };
};