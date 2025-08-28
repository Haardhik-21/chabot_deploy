// types/index.ts
export interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: Date;
  isStreaming?: boolean;
}

export interface UploadedFile {
  filename: string;
  chunk_count?: number;
  sample_text?: string;
}

export interface FileUploadResponse {
  message: string;
  filenames: string[];
  total_files: number;
  healthcare_files: string[];
  rejected_files: RejectedFile[];
}

export interface RejectedFile {
  filename: string;
  reason: string;
}

export interface FileListResponse {
  files: string[];
  total_files: number;
  total_chunks: number;
  file_details: UploadedFile[];
}

export interface ApiError {
  detail: string;
}