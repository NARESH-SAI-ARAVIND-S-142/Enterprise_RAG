"use client";

import { use } from "react";
import ChatInterface from "@/components/chat/ChatInterface";

export default function ChatPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);

  return <ChatInterface sessionId={sessionId} />;
}
