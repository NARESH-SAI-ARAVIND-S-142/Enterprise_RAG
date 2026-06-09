"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useChatStore } from "@/store/chatStore";
import { chatApi } from "@/lib/api";
import { ChatWebSocket } from "@/lib/websocket";
import MessageBubble from "./MessageBubble";
import StreamingIndicator from "./StreamingIndicator";
import SourcePanel from "./SourcePanel";
import type { Citation, ChatMessage } from "@/store/chatStore";

interface Props {
  sessionId: string;
}

const MODELS = [
  { value: "llama-3.1-8b-instant", label: "LLaMA 3.1 8B" },
  { value: "llama-3.3-70b-versatile", label: "LLaMA 3.3 70B" },
  { value: "gemma2-9b-it", label: "Gemma2 9B" },
];

export default function ChatInterface({ sessionId }: Props) {
  const {
    messages, isStreaming, streamingContent, currentStatus,
    selectedModel, selectedDocumentIds,
    addMessage, startStreaming, stopStreaming, appendStreamToken,
    setStreamingStatus, setSelectedModel, setMessages,
  } = useChatStore();

  const [input, setInput] = useState("");
  const [allCitations, setAllCitations] = useState<Citation[]>([]);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<ChatWebSocket | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load existing messages
  useEffect(() => {
    const loadMessages = async () => {
      try {
        const { data } = await chatApi.getMessages(sessionId);
        setMessages(data.map((m: any) => ({
          ...m,
          citations: m.citations || [],
        })));
        // Collect all citations
        const cites = data.flatMap((m: any) => m.citations || []);
        setAllCitations(cites);
      } catch {}
    };
    if (sessionId !== "new") loadMessages();
  }, [sessionId, setMessages]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const handleSend = useCallback(async () => {
    const query = input.trim();
    if (!query || isStreaming) return;
    setInput("");

    // Add user message
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query,
      citations: [],
      confidence_score: null,
      faithfulness_score: null,
      model_used: null,
      feedback: null,
      created_at: new Date().toISOString(),
    };
    addMessage(userMsg);
    startStreaming();

    // Use REST fallback (more reliable for now)
    try {
      const { data } = await chatApi.query(query, selectedDocumentIds, selectedModel);
      const citations = data.citations || [];
      setAllCitations((prev) => [...prev, ...citations]);
      stopStreaming(data.answer, citations, data.confidence_score || 0);
    } catch (err: any) {
      stopStreaming(
        `Error: ${err.response?.data?.detail || "Failed to get response"}`,
        [], 0
      );
    }
  }, [input, isStreaming, selectedDocumentIds, selectedModel, addMessage, startStreaming, stopStreaming]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFeedback = async (messageId: string, feedback: "thumbs_up" | "thumbs_down") => {
    try {
      await chatApi.submitFeedback(messageId, feedback);
    } catch {}
  };

  return (
    <div className="h-screen flex">
      {/* Chat Pane (65%) */}
      <div className="flex-[65] flex flex-col min-w-0" style={{ borderRight: "1px solid hsl(var(--border))" }}>
        {/* Chat Header */}
        <div className="px-6 py-3 flex items-center justify-between shrink-0"
          style={{ borderBottom: "1px solid hsl(var(--border))", background: "hsl(var(--card))" }}>
          <h2 className="text-sm font-semibold" style={{ color: "hsl(var(--foreground))" }}>Chat</h2>
          <div className="flex items-center gap-3">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="text-xs px-2 py-1 rounded-md outline-none"
              style={{ background: "hsl(var(--input))", color: "hsl(var(--foreground))", border: "1px solid hsl(var(--border))" }}>
              {MODELS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.length === 0 && !isStreaming && (
            <div className="h-full flex items-center justify-center">
              <div className="text-center">
                <span className="text-5xl mb-4 block">🧠</span>
                <h3 className="text-lg font-semibold" style={{ color: "hsl(var(--foreground))" }}>
                  Start a conversation
                </h3>
                <p className="text-sm mt-1 max-w-md" style={{ color: "hsl(var(--muted-foreground))" }}>
                  Ask questions about your uploaded documents. DocuMind will search,
                  verify, and cite sources for every answer.
                </p>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onCitationClick={setSelectedCitation}
              onFeedback={handleFeedback}
            />
          ))}

          {/* Streaming indicator */}
          <AnimatePresence>
            {isStreaming && (
              <div>
                {streamingContent && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    className="flex items-start gap-3 mb-4">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0"
                      style={{ background: "hsl(var(--secondary))", color: "white" }}>D</div>
                    <div className="rounded-2xl px-4 py-3"
                      style={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }}>
                      <p className="text-sm whitespace-pre-wrap" style={{ color: "hsl(var(--foreground))" }}>
                        {streamingContent}
                      </p>
                    </div>
                  </motion.div>
                )}
                <StreamingIndicator status={currentStatus} />
              </div>
            )}
          </AnimatePresence>

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="px-6 py-4 shrink-0" style={{ borderTop: "1px solid hsl(var(--border))", background: "hsl(var(--card))" }}>
          <div className="flex items-end gap-3">
            <textarea
              ref={inputRef}
              id="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your documents..."
              rows={1}
              disabled={isStreaming}
              className="flex-1 resize-none px-4 py-2.5 rounded-xl outline-none text-sm transition-all focus:ring-2"
              style={{
                background: "hsl(var(--input))",
                border: "1px solid hsl(var(--border))",
                color: "hsl(var(--foreground))",
                maxHeight: "120px",
              }}
            />
            <button
              id="chat-send"
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              className="px-4 py-2.5 rounded-xl font-medium text-sm transition-all hover:opacity-90 disabled:opacity-40 shrink-0"
              style={{ background: "hsl(var(--primary))", color: "white" }}>
              {isStreaming ? "..." : "Send"}
            </button>
          </div>
        </div>
      </div>

      {/* Source Pane (35%) */}
      <div className="flex-[35] min-w-0" style={{ background: "hsl(var(--card))" }}>
        <SourcePanel citations={allCitations} selectedCitation={selectedCitation} />
      </div>
    </div>
  );
}
