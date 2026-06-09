"use client";

import { motion } from "framer-motion";
import { getConfidenceColor } from "@/lib/utils";
import type { ChatMessage, Citation } from "@/store/chatStore";

interface Props {
  message: ChatMessage;
  onCitationClick?: (citation: Citation) => void;
  onFeedback?: (messageId: string, feedback: "thumbs_up" | "thumbs_down") => void;
}

export default function MessageBubble({ message, onCitationClick, onFeedback }: Props) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
    >
      <div className={`max-w-[80%] ${isUser ? "order-2" : ""}`}>
        {/* Avatar */}
        <div className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
          <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0"
            style={{
              background: isUser ? "hsl(var(--primary))" : "hsl(var(--secondary))",
              color: "white",
            }}>
            {isUser ? "U" : "D"}
          </div>

          <div className="flex-1 min-w-0">
            {/* Message Content */}
            <div className="rounded-2xl px-4 py-3"
              style={{
                background: isUser ? "hsl(var(--primary))" : "hsl(var(--card))",
                color: isUser ? "white" : "hsl(var(--foreground))",
                border: isUser ? "none" : "1px solid hsl(var(--border))",
              }}>
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
            </div>

            {/* Assistant metadata */}
            {!isUser && (
              <div className="mt-2 flex flex-wrap items-center gap-3">
                {/* Confidence score */}
                {message.confidence_score != null && (
                  <span className={`text-xs font-medium ${getConfidenceColor(message.confidence_score)}`}>
                    ● {(message.confidence_score * 100).toFixed(0)}% confident
                  </span>
                )}

                {/* Model */}
                {message.model_used && (
                  <span className="text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>
                    {message.model_used}
                  </span>
                )}

                {/* Feedback */}
                {onFeedback && (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => onFeedback(message.id, "thumbs_up")}
                      className={`p-1 rounded text-xs transition-all hover:opacity-80 ${message.feedback === "thumbs_up" ? "opacity-100" : "opacity-40"}`}>
                      👍
                    </button>
                    <button
                      onClick={() => onFeedback(message.id, "thumbs_down")}
                      className={`p-1 rounded text-xs transition-all hover:opacity-80 ${message.feedback === "thumbs_down" ? "opacity-100" : "opacity-40"}`}>
                      👎
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Citations */}
            {!isUser && message.citations && message.citations.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {message.citations.map((cite, i) => (
                  <button
                    key={cite.chunk_id || i}
                    onClick={() => onCitationClick?.(cite)}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-all hover:opacity-80"
                    style={{ background: "hsla(var(--secondary), 0.15)", color: "hsl(var(--secondary))" }}>
                    📎 {cite.source_file}{cite.page_number ? `, p.${cite.page_number}` : ""}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
