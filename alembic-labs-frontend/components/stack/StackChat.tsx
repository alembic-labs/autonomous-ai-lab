"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { StackIntro } from "./StackIntro";
import { StackMessage } from "./StackMessage";
import { EXAMPLE_STACK } from "@/lib/prompts";
import type { ChatMessage } from "@/lib/types";

const STORAGE_KEY = "alembic-stack-chat-v1";
const MAX_TEXTAREA_ROWS = 6;

function uid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

function buildMessage(role: ChatMessage["role"], content: string): ChatMessage {
  return {
    id: uid(),
    role,
    content,
    timestamp: new Date().toISOString(),
  };
}

interface StreamEvent {
  type: "delta" | "error" | "done";
  text?: string;
  message?: string;
}

async function streamCompletion(
  messages: ChatMessage[],
  onDelta: (chunk: string) => void,
  onError: (msg: string) => void,
): Promise<void> {
  const res = await fetch("/api/stack", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
    }),
  });
  if (!res.ok || !res.body) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data?.error) msg = data.error;
    } catch {
      /* ignore parse errors */
    }
    onError(msg);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const block of events) {
      const line = block.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const json = line.slice(5).trim();
      if (!json) continue;
      let parsed: StreamEvent;
      try {
        parsed = JSON.parse(json) as StreamEvent;
      } catch {
        continue;
      }
      if (parsed.type === "delta" && parsed.text) onDelta(parsed.text);
      else if (parsed.type === "error") onError(parsed.message ?? "unknown error");
    }
  }
}

export function StackChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamId, setStreamId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Hydrate from localStorage
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as ChatMessage[];
        if (Array.isArray(parsed)) setMessages(parsed);
      }
    } catch {
      /* ignore */
    }
    setHydrated(true);
  }, []);

  // Persist
  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {
      /* quota or disabled */
    }
  }, [messages, hydrated]);

  // Autoscroll on new messages
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streaming]);

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    const lineHeight = 22;
    const maxHeight = lineHeight * MAX_TEXTAREA_ROWS + 24;
    ta.style.height = `${Math.min(ta.scrollHeight, maxHeight)}px`;
  }, [input]);

  const send = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || streaming) return;
      setError(null);
      const userMsg = buildMessage("user", trimmed);
      const assistantMsg = buildMessage("assistant", "");
      setStreamId(assistantMsg.id);
      setStreaming(true);
      setInput("");
      const next = [...messages, userMsg, assistantMsg];
      setMessages(next);

      try {
        await streamCompletion(
          [...messages, userMsg],
          (chunk) =>
            setMessages((curr) =>
              curr.map((m) =>
                m.id === assistantMsg.id
                  ? { ...m, content: m.content + chunk }
                  : m,
              ),
            ),
          (errMsg) => setError(errMsg),
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "unknown error");
      } finally {
        setStreaming(false);
        setStreamId(null);
      }
    },
    [messages, streaming],
  );

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    void send(input);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim()) void send(input);
    }
  };

  const clearChat = () => {
    if (!window.confirm("clear current conversation?")) return;
    setMessages([]);
    setError(null);
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  };

  const showIntro = useMemo(() => messages.length === 0, [messages]);

  return (
    <div>
      {showIntro ? (
        <StackIntro
          onTryExample={() => setInput(EXAMPLE_STACK)}
          onStartFresh={() => textareaRef.current?.focus()}
        />
      ) : (
        <div className="space-y-2">
          {messages.map((m) => (
            <StackMessage
              key={m.id}
              message={m}
              streaming={streaming && m.id === streamId}
            />
          ))}
          <div ref={endRef} />
        </div>
      )}

      {error ? (
        <div className="border border-status-failed/40 bg-bg-surface text-status-failed text-small p-3 mt-4">
          {`// ${error}`}
        </div>
      ) : null}

      <form
        onSubmit={onSubmit}
        className="mt-8 border-t border-border-subtle pt-6 sticky bottom-0 bg-bg/95 backdrop-blur"
      >
        <label className="block">
          <span className="sr-only">describe your stack</span>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            disabled={streaming}
            placeholder='describe your stack: e.g. "BPC-157 250mcg morning, TB-500 2mg twice/wk, MOTS-c..."'
            className="input-mono resize-none w-full bg-bg-surface min-h-[64px]"
          />
        </label>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p className="text-text-muted text-small">
            in silico analysis · not medical advice
          </p>
          <div className="flex items-center gap-3">
            {messages.length > 0 ? (
              <button
                type="button"
                onClick={clearChat}
                className="text-text-muted hover:text-status-failed text-small uppercase tracking-wider transition-colors"
              >
                [ clear chat ]
              </button>
            ) : null}
            <button
              type="submit"
              disabled={streaming || !input.trim()}
              className="btn-bracket text-small"
            >
              <span className="text-text-muted">[</span>
              <span>{streaming ? "analyzing..." : "analyze →"}</span>
              <span className="text-text-muted">]</span>
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
