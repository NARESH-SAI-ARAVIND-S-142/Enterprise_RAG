"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { useAuthStore } from "@/store/authStore";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const { register, isLoading, error, clearError } = useAuthStore();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await register(email, password, fullName || undefined);
      router.push("/");
    } catch {}
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: "hsl(var(--background))" }}>
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-80 h-80 rounded-full opacity-20 blur-[100px]" style={{ background: "hsl(var(--accent))" }} />
        <div className="absolute -bottom-40 -right-40 w-80 h-80 rounded-full opacity-15 blur-[100px]" style={{ background: "hsl(var(--primary))" }} />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold gradient-text mb-2">DocuMind 2.0</h1>
          <p style={{ color: "hsl(var(--muted-foreground))" }}>Create your account</p>
        </div>

        <div className="glass-card p-8">
          <h2 className="text-2xl font-semibold mb-6" style={{ color: "hsl(var(--foreground))" }}>Get started</h2>

          {error && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="mb-4 p-3 rounded-lg text-sm"
              style={{ background: "hsla(var(--danger), 0.15)", color: "hsl(var(--danger))", border: "1px solid hsla(var(--danger), 0.3)" }}
            >{error}</motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: "hsl(var(--muted-foreground))" }}>Full Name</label>
              <input id="register-name" type="text" value={fullName} onChange={(e) => setFullName(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg outline-none transition-all focus:ring-2"
                style={{ background: "hsl(var(--input))", border: "1px solid hsl(var(--border))", color: "hsl(var(--foreground))" }}
                placeholder="John Doe" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: "hsl(var(--muted-foreground))" }}>Email</label>
              <input id="register-email" type="email" value={email} onChange={(e) => { setEmail(e.target.value); clearError(); }}
                required className="w-full px-4 py-2.5 rounded-lg outline-none transition-all focus:ring-2"
                style={{ background: "hsl(var(--input))", border: "1px solid hsl(var(--border))", color: "hsl(var(--foreground))" }}
                placeholder="you@example.com" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5" style={{ color: "hsl(var(--muted-foreground))" }}>Password</label>
              <input id="register-password" type="password" value={password} onChange={(e) => { setPassword(e.target.value); clearError(); }}
                required minLength={8} className="w-full px-4 py-2.5 rounded-lg outline-none transition-all focus:ring-2"
                style={{ background: "hsl(var(--input))", border: "1px solid hsl(var(--border))", color: "hsl(var(--foreground))" }}
                placeholder="Min. 8 characters" />
            </div>
            <button id="register-submit" type="submit" disabled={isLoading}
              className="w-full py-2.5 rounded-lg font-semibold transition-all hover:opacity-90 disabled:opacity-50"
              style={{ background: "hsl(var(--primary))", color: "white" }}
            >
              {isLoading ? "Creating account..." : "Create Account"}
            </button>
          </form>

          <p className="text-center mt-6 text-sm" style={{ color: "hsl(var(--muted-foreground))" }}>
            Already have an account?{" "}
            <Link href="/login" className="font-medium hover:underline" style={{ color: "hsl(var(--primary))" }}>Sign in</Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
