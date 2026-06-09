"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { documentsApi } from "@/lib/api";
import { formatFileSize, formatDate, getStatusColor } from "@/lib/utils";

interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number | null;
  page_count: number | null;
  status: string;
  progress: number;
  chunk_count: number | null;
  created_at: string;
}

interface Props {
  document: Document;
  onDelete: (id: string) => void;
}

export default function DocumentCard({ document: doc, onDelete }: Props) {
  const router = useRouter();
  const [progress, setProgress] = useState(doc.progress);
  const [status, setStatus] = useState(doc.status);
  const [deleting, setDeleting] = useState(false);

  // Poll for status updates during ingestion
  useEffect(() => {
    if (status === "ready" || status === "failed") return;

    const interval = setInterval(async () => {
      try {
        const { data } = await documentsApi.getStatus(doc.id);
        setStatus(data.status);
        setProgress(data.progress);
        if (data.status === "ready" || data.status === "failed") {
          clearInterval(interval);
        }
      } catch {}
    }, 2000);

    return () => clearInterval(interval);
  }, [doc.id, status]);

  const handleDelete = async () => {
    if (!confirm("Delete this document? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await documentsApi.delete(doc.id);
      onDelete(doc.id);
    } catch { setDeleting(false); }
  };

  const handleChat = async () => {
    router.push(`/chat/new?docs=${doc.id}`);
  };

  const fileIcon: Record<string, string> = {
    pdf: "📕", docx: "📘", doc: "📘", txt: "📝",
  };

  const isProcessing = !["ready", "failed"].includes(status);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="glass-card p-5 flex flex-col gap-3 group"
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-2xl shrink-0">{fileIcon[doc.file_type] || "📄"}</span>
          <div className="min-w-0">
            <h3 className="font-semibold text-sm truncate" style={{ color: "hsl(var(--foreground))" }}>
              {doc.filename}
            </h3>
            <p className="text-xs mt-0.5" style={{ color: "hsl(var(--muted-foreground))" }}>
              {doc.file_size_bytes ? formatFileSize(doc.file_size_bytes) : "—"}
              {doc.page_count ? ` • ${doc.page_count} pages` : ""}
            </p>
          </div>
        </div>

        {/* Status Badge */}
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium text-white ${getStatusColor(status)} ${isProcessing ? "status-active" : ""}`}>
          <span className="w-1.5 h-1.5 rounded-full bg-white/80" />
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </span>
      </div>

      {/* Progress Bar (during ingestion) */}
      {isProcessing && (
        <div className="w-full rounded-full h-1.5 overflow-hidden" style={{ background: "hsl(var(--input))" }}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5 }}
            className="h-full rounded-full progress-gradient"
          />
        </div>
      )}

      {/* Stats */}
      {status === "ready" && (
        <div className="flex items-center gap-4 text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>
          <span>{doc.chunk_count || 0} chunks</span>
          <span>•</span>
          <span>{formatDate(doc.created_at)}</span>
        </div>
      )}

      {status === "failed" && (
        <p className="text-xs" style={{ color: "hsl(var(--danger))" }}>Ingestion failed. Try re-uploading.</p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-auto pt-2" style={{ borderTop: "1px solid hsl(var(--border))" }}>
        {status === "ready" && (
          <button onClick={handleChat}
            className="flex-1 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-90"
            style={{ background: "hsl(var(--primary))", color: "white" }}>
            💬 Chat
          </button>
        )}
        <button onClick={handleDelete} disabled={deleting}
          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:opacity-80 disabled:opacity-50"
          style={{ background: "hsla(var(--danger), 0.15)", color: "hsl(var(--danger))" }}>
          {deleting ? "..." : "🗑"}
        </button>
      </div>
    </motion.div>
  );
}
