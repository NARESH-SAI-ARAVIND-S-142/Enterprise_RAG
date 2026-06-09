"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { Citation } from "@/store/chatStore";

interface Props {
  citations: Citation[];
  selectedCitation: Citation | null;
}

export default function SourcePanel({ citations, selectedCitation }: Props) {
  if (citations.length === 0 && !selectedCitation) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="text-center">
          <span className="text-4xl mb-3 block">🔍</span>
          <p className="text-sm font-medium" style={{ color: "hsl(var(--foreground))" }}>
            Source Viewer
          </p>
          <p className="text-xs mt-1" style={{ color: "hsl(var(--muted-foreground))" }}>
            Click a citation to view the source
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-4 py-3" style={{ borderBottom: "1px solid hsl(var(--border))" }}>
        <h3 className="text-sm font-semibold" style={{ color: "hsl(var(--foreground))" }}>
          Sources ({citations.length})
        </h3>
      </div>

      {/* Source List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        <AnimatePresence>
          {citations.map((cite, i) => (
            <motion.div
              key={cite.chunk_id || i}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="rounded-lg p-3 transition-all"
              style={{
                background: selectedCitation?.chunk_id === cite.chunk_id
                  ? "hsla(var(--primary), 0.15)"
                  : "hsl(var(--card))",
                border: `1px solid ${
                  selectedCitation?.chunk_id === cite.chunk_id
                    ? "hsl(var(--primary))"
                    : "hsl(var(--border))"
                }`,
              }}
            >
              {/* Source header */}
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold" style={{ color: "hsl(var(--secondary))" }}>
                  📎 {cite.source_file}
                </span>
                {cite.page_number && (
                  <span className="text-xs px-1.5 py-0.5 rounded"
                    style={{ background: "hsla(var(--primary), 0.1)", color: "hsl(var(--primary))" }}>
                    Page {cite.page_number}
                  </span>
                )}
              </div>

              {/* Source text */}
              <p className="text-xs leading-relaxed" style={{ color: "hsl(var(--muted-foreground))" }}>
                {cite.text}
              </p>

              {/* Relevance */}
              {cite.relevance_score > 0 && (
                <div className="mt-2 flex items-center gap-1">
                  <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ background: "hsl(var(--input))" }}>
                    <div className="h-full rounded-full"
                      style={{
                        width: `${Math.min(cite.relevance_score * 100, 100)}%`,
                        background: "hsl(var(--success))",
                      }} />
                  </div>
                  <span className="text-[10px]" style={{ color: "hsl(var(--muted-foreground))" }}>
                    {(cite.relevance_score * 100).toFixed(0)}%
                  </span>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
