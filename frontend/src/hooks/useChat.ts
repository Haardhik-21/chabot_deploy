// hooks/useChat.ts
import { useState, useCallback } from 'react';
import { apiClient, ApiError } from '../utils/api';
import { Message } from '../types';

export const useChat = () => {

  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(async (question: string, entertainmentEnabled: boolean = false) => {

    if (!question.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: question,
      isUser: true,
      timestamp: new Date(),
    };

    const botMessage: Message = {
      id: (Date.now() + 1).toString(),
      content: '',
      isUser: false,
      timestamp: new Date(),
      isStreaming: true,
    };

    setMessages(prev => [...prev, userMessage, botMessage]);
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.askQuestion(question, entertainmentEnabled);

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = '';

      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        accumulatedText += chunk;
        
        // Update the bot message with accumulated text
        setMessages(prev => 
          prev.map(msg => 
            msg.id === botMessage.id 
              ? { ...msg, content: accumulatedText, isStreaming: true }
              : msg
          )
        );
      }

      // Mark streaming as complete
      setMessages(prev => 
        prev.map(msg => 
          msg.id === botMessage.id 
            ? { ...msg, isStreaming: false }
            : msg
        )
      );

    } catch (err) {
      const errorMessage = err instanceof ApiError ? err.message : 'Failed to send message';
      setError(errorMessage);
      
      // Update bot message with error
      setMessages(prev => 
        prev.map(msg => 
          msg.id === botMessage.id 
            ? { 
                ...msg, 
                content: 'Sorry, I encountered an error. Please try again.',
                isStreaming: false 
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearMessages = useCallback(async () => {
    try {
      await apiClient.newSession();
      setMessages([]);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start new session');
    }
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
  };
};