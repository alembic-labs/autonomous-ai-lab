"use client";

import ReactMarkdown from "react-markdown";
import type { ChatMessage } from "@/lib/types";

interface StackMessageProps {
  message: ChatMessage;
  streaming?: boolean;
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function StackMessage({ message, streaming = false }: StackMessageProps) {
  if (message.role === "user") {
    return (
      <div className="flex flex-col items-end mb-6 group">
        <div className="text-text-muted text-small uppercase tracking-wider mb-1.5">
          &gt; user &gt;&gt;{" "}
          <span className="opacity-0 group-hover:opacity-100 transition-opacity">
            {formatTime(message.timestamp)}
          </span>
        </div>
        <div className="max-w-[85%] sm:max-w-[70%] bg-bg-surface border border-border-accent p-4 sm:p-5 text-text-primary text-body whitespace-pre-wrap break-words">
          {message.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-start mb-6 group">
      <div className="text-brand text-small uppercase tracking-wider mb-1.5">
        &lt; alembic &lt;&lt;{" "}
        <span className="text-text-muted opacity-0 group-hover:opacity-100 transition-opacity">
          {formatTime(message.timestamp)}
        </span>
      </div>
      <div className="prose-mono w-full max-w-none">
        <ReactMarkdown>
          {message.content + (streaming ? " ▍" : "")}
        </ReactMarkdown>
      </div>
    </div>
  );
}
