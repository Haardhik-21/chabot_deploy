// components/Chat/ChatContainer.tsx
import React, { useEffect, useState } from 'react';
import { useChat } from '../../hooks/useChat';
import { useFileManager } from '../../hooks/useFileManager';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { FileUpload } from '../FileUpload/FileUpload';
import { FileList } from '../FileUpload/FileList';
import { Button } from '../UI/Button';
import { apiClient } from '../../utils/api';

export const ChatContainer: React.FC = () => {
  const { messages, isLoading, error, sendMessage, clearMessages } = useChat();
  const { files, loading, error: filesError, fetchFiles, deleteFile, clearAllFiles } = useFileManager();
  const [showFilePanel, setShowFilePanel] = useState(false);
  const [ingestUrl, setIngestUrl] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [ingestMsg, setIngestMsg] = useState<string | null>(null);
  const [webSources, setWebSources] = useState<{ total_urls: number; total_chunks: number; sources: { url: string; chunks: number }[] } | null>(null);
  const [webLoading, setWebLoading] = useState(false);
  const [webError, setWebError] = useState<string | null>(null);
  const [entertainmentEnabled, setEntertainmentEnabled] = useState(false);

  const handleSendMessage = (message: string) => {
    sendMessage(message, entertainmentEnabled);
  };

  const handleNewSession = () => {
    clearMessages();
  };

  const handleFileUploadComplete = () => {
    // Refresh file list so UI updates and chat input becomes enabled
    fetchFiles();
  };

  const handleIngest = async () => {
    if (!ingestUrl || ingesting) return;
    setIngesting(true);
    setIngestMsg(null);
    try {
      const res = await apiClient.ingestUrl(ingestUrl);
      setIngestMsg(`Ingested successfully: ${res.stored || 0} chunks`);
      setIngestUrl('');
      // refresh web sources list
      await loadWebSources();
    } catch (e: any) {
      setIngestMsg(e?.message || 'Failed to ingest');
    } finally {
      setIngesting(false);
    }
  };

  const loadWebSources = async () => {
    setWebLoading(true);
    setWebError(null);
    try {
      const data = await apiClient.listWebSources();
      setWebSources(data);
    } catch (e: any) {
      setWebError(e?.message || 'Failed to fetch web sources');
    } finally {
      setWebLoading(false);
    }
  };

  const handleDeleteWeb = async (url: string) => {
    try {
      await apiClient.deleteWebSource(url);
      await loadWebSources();
    } catch (e: any) {
      setWebError(e?.message || 'Failed to delete');
    }
  };

  useEffect(() => {
    loadWebSources();
  }, []);

  return (
    <div className="h-screen bg-gray-900 flex">
      {/* Side Panel for File Management */}
      <div className={`${showFilePanel ? 'w-96' : 'w-0'} transition-all duration-300 overflow-hidden border-r border-gray-700`}>
        <div className="h-full bg-gray-800 p-4 overflow-y-auto">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-white mb-4">File Management</h2>
            <FileUpload onUploadComplete={handleFileUploadComplete} />
          </div>
          {/* Minimal URL Ingest (stored separately; does not affect current chat) */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-300 mb-2">Ingest Web URL</h3>
            <div className="flex space-x-2">
              <input
                className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                type="url"
                placeholder="https://example.com/article"
                value={ingestUrl}
                onChange={(e) => setIngestUrl(e.target.value)}
              />
              <Button onClick={handleIngest} size="sm" disabled={ingesting || !ingestUrl}>
                {ingesting ? 'Ingesting...' : 'Ingest'}
              </Button>
            </div>
            {ingestMsg && (
              <p className="mt-2 text-xs text-gray-400">{ingestMsg}</p>
            )}
          </div>
          {/* Web sources list */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-300 mb-2">Ingested URLs</h3>
            {webLoading ? (
              <p className="text-xs text-gray-500">Loading...</p>
            ) : webError ? (
              <p className="text-xs text-red-400">{webError}</p>
            ) : (
              <div className="space-y-2">
                {(webSources?.sources?.length || 0) === 0 ? (
                  <p className="text-xs text-gray-500">No URLs ingested yet</p>
                ) : (
                  webSources!.sources.map((s) => (
                    <div key={s.url} className="flex items-center justify-between text-xs bg-gray-900 border border-gray-700 rounded px-2 py-1">
                      <a href={s.url} target="_blank" rel="noreferrer" className="truncate text-blue-300 hover:underline max-w-[220px]">{s.url}</a>
                      <div className="flex items-center space-x-2">
                        <span className="text-gray-400">{s.chunks} chunks</span>
                        <Button size="sm" variant="secondary" onClick={() => handleDeleteWeb(s.url)}>Remove</Button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
          <FileList
            files={files}
            loading={loading}
            error={filesError}
            onDelete={deleteFile}
            onClearAll={clearAllFiles}
          />
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-gray-800 border-b border-gray-700 px-4 py-3">
          <div className="flex items-center justify-between max-w-4xl mx-auto">
            <div className="flex items-center space-x-4">
              <Button
                onClick={() => setShowFilePanel(!showFilePanel)}
                variant="secondary"
                size="sm"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {showFilePanel ? 'Hide Files' : 'Manage Files'}
              </Button>

              <div className="text-white">
                <h1 className="text-lg font-semibold">Document Assistant</h1>
                {files && (
                  <p className="text-sm text-gray-400">
                    {files.total_files} files • {files.total_chunks} chunks
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center space-x-2">
              {/* Entertainment Mode Toggle */}
              <button
                onClick={() => setEntertainmentEnabled(v => !v)}
                className={`px-3 py-2 rounded text-sm border ${entertainmentEnabled ? 'bg-purple-600 text-white border-purple-500' : 'bg-gray-900 text-gray-200 border-gray-700'} hover:opacity-90`}
                title="Enable to ask entertainment-related questions"
                disabled={isLoading}
              >
                {entertainmentEnabled ? 'Entertainment: ON' : 'Entertainment: OFF'}
              </button>
              <Button
                onClick={handleNewSession}
                variant="secondary"
                size="sm"
                disabled={isLoading}
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                New Session
              </Button>
            </div>
          </div>
        </header>

        {/* Error Display */}
        {error && (
          <div className="bg-red-900/50 border-b border-red-700 px-4 py-3">
            <div className="max-w-4xl mx-auto">
              <p className="text-red-300 text-sm">{error}</p>
            </div>
          </div>
        )}

        {/* Messages Area */}
        <MessageList messages={messages} />

        {/* Chat Input */}
        <ChatInput
          onSendMessage={handleSendMessage}
          disabled={!entertainmentEnabled && (!files || (files.total_files === 0 && (webSources?.total_urls || 0) === 0))}
          isLoading={isLoading}
        />

        {/* No Sources Warning */}
        {(!entertainmentEnabled) && files && files.total_files === 0 && (webSources?.total_urls || 0) === 0 && (
          <div className="bg-yellow-900/30 border-t border-yellow-700 px-4 py-2">
            <div className="max-w-4xl mx-auto text-center">
              <p className="text-yellow-300 text-sm">
                Please upload documents or ingest a web URL before asking questions
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};