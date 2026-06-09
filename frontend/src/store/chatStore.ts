import { create } from "zustand";

export interface Citation {
  chunk_id: string;
  text: string;
  page_number: number | null;
  source_file: string;
  document_id: string;
  relevance_score: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Citation[];
  confidence_score: number | null;
  faithfulness_score: number | null;
  model_used: string | null;
  feedback: string | null;
  created_at: string;
  isStreaming?: boolean;
}

interface ChatState {
  sessions: { id: string; title: string; created_at: string }[];
  currentSessionId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  streamingContent: string;
  currentStatus: string;
  selectedDocumentIds: string[];
  selectedModel: string;

  setSessions: (sessions: any[]) => void;
  setCurrentSession: (sessionId: string) => void;
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  appendStreamToken: (token: string) => void;
  setStreamingStatus: (status: string) => void;
  startStreaming: () => void;
  stopStreaming: (finalAnswer: string, citations: Citation[], confidence: number) => void;
  setSelectedDocuments: (ids: string[]) => void;
  setSelectedModel: (model: string) => void;
  clearChat: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  messages: [],
  isStreaming: false,
  streamingContent: "",
  currentStatus: "",
  selectedDocumentIds: [],
  selectedModel: "llama-3.1-8b-instant",

  setSessions: (sessions) => set({ sessions }),
  setCurrentSession: (sessionId) => set({ currentSessionId: sessionId }),
  setMessages: (messages) => set({ messages }),

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  appendStreamToken: (token) =>
    set((state) => ({ streamingContent: state.streamingContent + token })),

  setStreamingStatus: (status) => set({ currentStatus: status }),

  startStreaming: () =>
    set({ isStreaming: true, streamingContent: "", currentStatus: "Thinking..." }),

  stopStreaming: (finalAnswer, citations, confidence) =>
    set((state) => {
      const assistantMsg: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: "assistant",
        content: finalAnswer || state.streamingContent,
        citations,
        confidence_score: confidence,
        faithfulness_score: null,
        model_used: state.selectedModel,
        feedback: null,
        created_at: new Date().toISOString(),
      };
      return {
        messages: [...state.messages, assistantMsg],
        isStreaming: false,
        streamingContent: "",
        currentStatus: "",
      };
    }),

  setSelectedDocuments: (ids) => set({ selectedDocumentIds: ids }),
  setSelectedModel: (model) => set({ selectedModel: model }),
  clearChat: () => set({ messages: [], streamingContent: "", currentStatus: "" }),
}));
