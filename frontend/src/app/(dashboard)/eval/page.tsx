"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { evalApi } from "@/lib/api";

interface EvalResult {
  id: string;
  status: string;
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_precision: number | null;
  context_recall: number | null;
  answer_correctness: number | null;
  created_at: string;
}

function GaugeChart({ label, value, icon }: { label: string; value: number | null; icon: string }) {
  const score = value ?? 0;
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? "var(--success)" : score >= 0.6 ? "var(--warning)" : "var(--danger)";
  const circumference = 2 * Math.PI * 40;
  const offset = circumference - (score * circumference);

  return (
    <div className="glass-card p-5 flex flex-col items-center gap-3">
      <div className="relative w-24 h-24">
        <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" fill="none" stroke="hsl(var(--input))" strokeWidth="6" />
          <motion.circle
            cx="50" cy="50" r="40" fill="none"
            stroke={`hsl(${color})`}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1, delay: 0.3 }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-bold" style={{ color: `hsl(${color})` }}>{pct}%</span>
        </div>
      </div>
      <div className="text-center">
        <span className="text-lg">{icon}</span>
        <p className="text-xs font-medium mt-1" style={{ color: "hsl(var(--foreground))" }}>{label}</p>
      </div>
    </div>
  );
}

export default function EvaluationPage() {
  const [history, setHistory] = useState<EvalResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const { data } = await evalApi.getHistory();
      setHistory(data);
    } catch {} finally { setLoading(false); }
  };

  const latestResult = history[0];

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: "hsl(var(--foreground))" }}>
            Evaluation Dashboard
          </h1>
          <p className="mt-1" style={{ color: "hsl(var(--muted-foreground))" }}>
            RAGAS metrics and quality tracking
          </p>
        </div>
        <button
          onClick={async () => {
            setRunning(true);
            try {
              await evalApi.run([]);
              await fetchHistory();
            } catch {} finally { setRunning(false); }
          }}
          disabled={running}
          className="px-5 py-2.5 rounded-xl font-medium text-sm transition-all hover:opacity-90 disabled:opacity-50"
          style={{ background: "hsl(var(--primary))", color: "white" }}>
          {running ? "Running..." : "▶ Run Evaluation"}
        </button>
      </div>

      {/* Metric Gauges */}
      {latestResult ? (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <GaugeChart label="Faithfulness" value={latestResult.faithfulness} icon="🎯" />
          <GaugeChart label="Answer Relevancy" value={latestResult.answer_relevancy} icon="📝" />
          <GaugeChart label="Context Precision" value={latestResult.context_precision} icon="🔬" />
          <GaugeChart label="Context Recall" value={latestResult.context_recall} icon="📦" />
          <GaugeChart label="Correctness" value={latestResult.answer_correctness} icon="✅" />
        </div>
      ) : !loading ? (
        <div className="glass-card p-12 text-center mb-8">
          <span className="text-5xl block mb-3">📊</span>
          <p className="font-medium" style={{ color: "hsl(var(--foreground))" }}>No evaluations yet</p>
          <p className="text-sm mt-1" style={{ color: "hsl(var(--muted-foreground))" }}>
            Upload documents and run an evaluation to see metrics
          </p>
        </div>
      ) : null}

      {/* History Table */}
      {history.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="px-5 py-3" style={{ borderBottom: "1px solid hsl(var(--border))" }}>
            <h3 className="text-sm font-semibold" style={{ color: "hsl(var(--foreground))" }}>
              Evaluation History
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid hsl(var(--border))" }}>
                  {["Date", "Status", "Faith.", "Relev.", "Prec.", "Recall", "Correct."].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-medium"
                      style={{ color: "hsl(var(--muted-foreground))" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map((r) => (
                  <tr key={r.id} className="transition-colors hover:opacity-80"
                    style={{ borderBottom: "1px solid hsl(var(--border))" }}>
                    <td className="px-4 py-2.5 text-xs" style={{ color: "hsl(var(--foreground))" }}>
                      {new Date(r.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        r.status === "completed" ? "text-emerald-400 bg-emerald-400/10" : "text-amber-400 bg-amber-400/10"
                      }`}>{r.status}</span>
                    </td>
                    {[r.faithfulness, r.answer_relevancy, r.context_precision, r.context_recall, r.answer_correctness].map((v, i) => (
                      <td key={i} className="px-4 py-2.5 text-xs font-mono"
                        style={{ color: v != null ? (v >= 0.8 ? "hsl(var(--success))" : v >= 0.6 ? "hsl(var(--warning))" : "hsl(var(--danger))") : "hsl(var(--muted))" }}>
                        {v != null ? (v * 100).toFixed(1) + "%" : "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {loading && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => <div key={i} className="shimmer rounded-xl h-16" />)}
        </div>
      )}
    </div>
  );
}
