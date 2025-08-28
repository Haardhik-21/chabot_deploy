// hooks/useFileManager.ts
import { useState, useEffect } from 'react';
import { apiClient, ApiError } from '../utils/api';
import { FileListResponse } from '../types';

export const useFileManager = () => {
  const [files, setFiles] = useState<FileListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchFiles = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getFiles();
      setFiles(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to fetch files');
    } finally {
      setLoading(false);
    }
  };

  const deleteFile = async (filename: string) => {
    setLoading(true);
    setError(null);
    try {
      // First, attempt the deletion. If this fails, report error.
      await apiClient.deleteFile(filename);
      // Optimistically update local state
      setFiles((prev) => {
        if (!prev) return prev;
        const nextFiles = prev.files.filter((f) => f !== filename);
        const nextDetails = prev.file_details.filter((d) => d.filename !== filename);
        const removed = prev.file_details.find((d) => d.filename === filename)?.chunk_count || 0;
        return {
          files: nextFiles,
          file_details: nextDetails,
          total_files: Math.max(0, prev.total_files - 1),
          total_chunks: Math.max(0, prev.total_chunks - removed),
        } as FileListResponse;
      });
      // Deletion succeeded. Now try to refresh, but don't mark the whole
      // operation as failed if refresh hits a transient error.
      try {
        await fetchFiles();
      } catch (refreshErr) {
        // Log or set a soft message if you have a toast system; do not setError here
        console.warn('File deleted, but failed to refresh list:', refreshErr);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to delete file');
    } finally {
      setLoading(false);
    }
  };

  const clearAllFiles = async () => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.clearAll();
      setFiles({ files: [], total_files: 0, total_chunks: 0, file_details: [] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to clear all files');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  return {
    files,
    loading,
    error,
    fetchFiles,
    deleteFile,
    clearAllFiles,
  };
};