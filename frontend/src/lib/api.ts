import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Request interceptor: attach JWT token
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Response interceptor: handle 401 and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem("refresh_token");
        if (refreshToken) {
          const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("refresh_token", data.refresh_token);
          originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
          return api(originalRequest);
        }
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

// ── Auth API ──────────────────────────────────────────────────
export const authApi = {
  register: (email: string, password: string, fullName?: string) =>
    api.post("/auth/register", { email, password, full_name: fullName }),

  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }),

  getMe: () => api.get("/auth/me"),
};

// ── Documents API ─────────────────────────────────────────────
export const documentsApi = {
  upload: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post("/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  list: (page = 1, perPage = 20, status?: string) =>
    api.get("/documents/", { params: { page, per_page: perPage, status } }),

  getStatus: (documentId: string) =>
    api.get(`/documents/${documentId}/status`),

  delete: (documentId: string) =>
    api.delete(`/documents/${documentId}`),
};

// ── Chat API ──────────────────────────────────────────────────
export const chatApi = {
  createSession: (title?: string, documentIds: string[] = []) =>
    api.post("/chat/sessions", { title, document_ids: documentIds }),

  listSessions: () => api.get("/chat/sessions"),

  getMessages: (sessionId: string) =>
    api.get(`/chat/sessions/${sessionId}/messages`),

  query: (query: string, documentIds: string[] = [], model?: string) =>
    api.post("/chat/query", { query, document_ids: documentIds, model }),

  submitFeedback: (messageId: string, feedback: "thumbs_up" | "thumbs_down") =>
    api.post(`/chat/messages/${messageId}/feedback`, { feedback }),

  deleteSession: (sessionId: string) =>
    api.delete(`/chat/sessions/${sessionId}`),
};

// ── Evaluation API ────────────────────────────────────────────
export const evalApi = {
  run: (documentIds: string[]) =>
    api.post("/eval/run", null, {
      params: { document_ids: documentIds },
    }),

  getResults: (evalId: string) => api.get(`/eval/results/${evalId}`),

  getHistory: () => api.get("/eval/history"),
};

export default api;
