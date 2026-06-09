"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { documentsApi } from "@/lib/api";

interface Props {
  onUploadComplete: () => void;
}

export default function DocumentUpload({ onUploadComplete }: Props) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    setUploadError(null);
    setUploading(true);

    for (const file of acceptedFiles) {
      try {
        await documentsApi.upload(file);
      } catch (err: any) {
        setUploadError(err.response?.data?.detail || `Failed to upload ${file.name}`);
      }
    }

    setUploading(false);
    onUploadComplete();
  }, [onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
    },
    maxSize: 50 * 1024 * 1024,
    disabled: uploading,
  });

  return (
    <div>
      <div
        {...getRootProps()}
        id="document-upload-zone"
        className="relative cursor-pointer rounded-xl p-8 text-center transition-all duration-300"
        style={{
          border: `2px dashed ${isDragActive ? "hsl(var(--primary))" : "hsl(var(--border))"}`,
          background: isDragActive ? "hsla(var(--primary), 0.05)" : "hsl(var(--card))",
        }}
      >
        <input {...getInputProps()} />

        <AnimatePresence mode="wait">
          {uploading ? (
            <motion.div key="uploading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col items-center gap-3">
              <div className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: "hsl(var(--primary))", borderTopColor: "transparent" }} />
              <p className="text-sm" style={{ color: "hsl(var(--muted-foreground))" }}>Uploading...</p>
            </motion.div>
          ) : (
            <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col items-center gap-3">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
                style={{ background: "hsla(var(--primary), 0.1)" }}>
                {isDragActive ? "📥" : "📁"}
              </div>
              <div>
                <p className="font-medium" style={{ color: "hsl(var(--foreground))" }}>
                  {isDragActive ? "Drop files here" : "Drag & drop documents"}
                </p>
                <p className="text-sm mt-1" style={{ color: "hsl(var(--muted-foreground))" }}>
                  or click to browse • PDF, DOCX, TXT • Max 50MB
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {uploadError && (
          <motion.p initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="mt-2 text-sm px-3 py-2 rounded-lg"
            style={{ color: "hsl(var(--danger))", background: "hsla(var(--danger), 0.1)" }}>
            {uploadError}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}
