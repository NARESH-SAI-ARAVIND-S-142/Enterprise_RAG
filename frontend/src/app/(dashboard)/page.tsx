"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { documentsApi } from "@/lib/api";
import DocumentUpload from "@/components/documents/DocumentUpload";
import DocumentCard from "@/components/documents/DocumentCard";

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

export default function DocumentLibraryPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");

  const fetchDocuments = useCallback(async () => {
    try {
      const { data } = await documentsApi.list(1, 50, statusFilter || undefined);
      setDocuments(data.documents);
    } catch (err) {
      console.error("Failed to fetch documents:", err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleDelete = (id: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
  };

  const statusOptions = ["", "queued", "parsing", "chunking", "embedding", "indexing", "ready", "failed"];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold" style={{ color: "hsl(var(--foreground))" }}>
          Document Library
        </h1>
        <p className="mt-1" style={{ color: "hsl(var(--muted-foreground))" }}>
          Upload, manage, and chat with your documents
        </p>
      </div>

      {/* Upload Zone */}
      <div className="mb-8">
        <DocumentUpload onUploadComplete={fetchDocuments} />
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          {statusOptions.map((s) => (
            <button
              key={s || "all"}
              onClick={() => setStatusFilter(s)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              style={{
                background: statusFilter === s ? "hsl(var(--primary))" : "hsl(var(--card))",
                color: statusFilter === s ? "white" : "hsl(var(--muted-foreground))",
                border: `1px solid ${statusFilter === s ? "hsl(var(--primary))" : "hsl(var(--border))"}`,
              }}
            >
              {s ? s.charAt(0).toUpperCase() + s.slice(1) : "All"}
            </button>
          ))}
        </div>
        <p className="text-sm" style={{ color: "hsl(var(--muted-foreground))" }}>
          {documents.length} document{documents.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Document Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="shimmer rounded-xl h-44" />
          ))}
        </div>
      ) : documents.length === 0 ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-20"
        >
          <span className="text-6xl mb-4 block">📭</span>
          <p className="text-lg font-medium" style={{ color: "hsl(var(--foreground))" }}>
            No documents yet
          </p>
          <p className="mt-1" style={{ color: "hsl(var(--muted-foreground))" }}>
            Upload your first document to get started
          </p>
        </motion.div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <AnimatePresence>
            {documents.map((doc) => (
              <DocumentCard key={doc.id} document={doc} onDelete={handleDelete} />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
