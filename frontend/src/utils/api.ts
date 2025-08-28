// utils/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  constructor(public message: string, public status?: number) {
    super(message);
    this.name = 'ApiError';
  }
}

export const apiClient = {
  // Upload files
  async uploadFiles(files: File[]) {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    const response = await fetch(`${API_BASE}/upload/`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new ApiError(error.detail || 'Upload failed', response.status);
    }

    return response.json();
  },

  // Get uploaded files list
  async getFiles() {
    const response = await fetch(`${API_BASE}/files/?t=${Date.now()}` , {
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache' },
    });
    if (!response.ok) {
      throw new ApiError('Failed to fetch files', response.status);
    }
    return response.json();
  },

  // Delete specific file
  async deleteFile(filename: string) {
    const response = await fetch(`${API_BASE}/files/delete/${encodeURIComponent(filename)}?t=${Date.now()}`, {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache' },
    });

    if (!response.ok) {
      throw new ApiError('Failed to delete file', response.status);
    }

    // Some servers may return 204 No Content; parse safely
    let data: any = null;
    try {
      data = await response.json();
    } catch (_) {
      data = { message: 'Deleted' };
    }
    return data;
  },

  // Clear all files and data
  async clearAll() {
    const response = await fetch(`${API_BASE}/clear-all/`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new ApiError('Failed to clear all data', response.status);
    }

    return response.json();
  },

  // Ask question (streaming)
  async askQuestion(question: string, entertainmentEnabled: boolean = false) {
    const response = await fetch(`${API_BASE}/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question, entertainment_enabled: entertainmentEnabled }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new ApiError(error.detail || 'Request failed', response.status);
    }

    return response;
  },

  // Start new session
  async newSession() {
    const response = await fetch(`${API_BASE}/new-session/`, {
      method: 'GET',
    });

    if (!response.ok) {
      throw new ApiError('Failed to start new session', response.status);
    }

    return response.json();
  },

  // Ingest a web URL (stored in a separate collection; does not affect current chat behavior)
  async ingestUrl(url: string) {
    const response = await fetch(`${API_BASE}/ingest-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Ingest failed' }));
      throw new ApiError(error.detail || 'Ingest failed', response.status);
    }
    return response.json();
  },

  async listWebSources() {
    const response = await fetch(`${API_BASE}/web-sources`, {
      method: 'GET',
    });
    if (!response.ok) {
      throw new ApiError('Failed to fetch web sources', response.status);
    }
    return response.json();
  },

  async deleteWebSource(url: string) {
    const response = await fetch(`${API_BASE}/web-sources`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to delete web source' }));
      throw new ApiError(error.detail || 'Failed to delete web source', response.status);
    }
    return response.json();
  },
};