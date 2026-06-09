export interface WSHandlers {
  onStatus: (content: string) => void;
  onToken: (content: string) => void;
  onSources: (content: any[]) => void;
  onConfidence: (score: number) => void;
  onAnswer: (content: string) => void;
  onDone: () => void;
  onError: (content: string) => void;
}

export class ChatWebSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnects = 3;
  private sessionId: string = "";
  private token: string = "";
  private handlers: WSHandlers | null = null;

  connect(sessionId: string, token: string, handlers: WSHandlers) {
    this.sessionId = sessionId;
    this.token = token;
    this.handlers = handlers;

    const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const url = `${wsBase}/chat/ws/${sessionId}?token=${token}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      console.log("WebSocket connected");
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        switch (data.type) {
          case "status":     handlers.onStatus(data.content); break;
          case "token":      handlers.onToken(data.content); break;
          case "sources":    handlers.onSources(data.content); break;
          case "confidence": handlers.onConfidence(data.content); break;
          case "answer":     handlers.onAnswer(data.content); break;
          case "done":       handlers.onDone(); break;
          case "error":      handlers.onError(data.content); break;
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    this.ws.onclose = (event) => {
      if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnects) {
        const delay = 1000 * Math.pow(2, this.reconnectAttempts);
        console.log(`WebSocket reconnecting in ${delay}ms...`);
        setTimeout(() => {
          this.reconnectAttempts++;
          this.connect(sessionId, token, handlers);
        }, delay);
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };
  }

  sendQuery(query: string, documentIds: string[]) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ query, document_ids: documentIds }));
    } else {
      console.error("WebSocket not connected");
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close(1000);
      this.ws = null;
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
