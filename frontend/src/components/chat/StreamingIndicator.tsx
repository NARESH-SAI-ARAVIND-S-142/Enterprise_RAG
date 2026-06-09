"use client";

import { motion } from "framer-motion";

interface Props {
  status: string;
}

export default function StreamingIndicator({ status }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="flex items-start gap-3 mb-4"
    >
      <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 pulse-glow"
        style={{ background: "hsl(var(--secondary))", color: "white" }}>
        D
      </div>
      <div className="rounded-2xl px-4 py-3"
        style={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }}>
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            <span className="typing-dot w-1.5 h-1.5 rounded-full" style={{ background: "hsl(var(--primary))" }} />
            <span className="typing-dot w-1.5 h-1.5 rounded-full" style={{ background: "hsl(var(--primary))" }} />
            <span className="typing-dot w-1.5 h-1.5 rounded-full" style={{ background: "hsl(var(--primary))" }} />
          </div>
          <span className="text-xs font-medium" style={{ color: "hsl(var(--muted-foreground))" }}>
            {status || "Thinking..."}
          </span>
        </div>
      </div>
    </motion.div>
  );
}
