import Anthropic from "@anthropic-ai/sdk";
import { NextRequest } from "next/server";
import { STACK_ANALYZER_SYSTEM_PROMPT } from "@/lib/prompts";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface IncomingMessage {
  role: "user" | "assistant";
  content: string;
}

interface IncomingPayload {
  messages: IncomingMessage[];
}

function sse(data: unknown): string {
  return `data: ${JSON.stringify(data)}\n\n`;
}

export async function POST(req: NextRequest): Promise<Response> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return new Response(
      JSON.stringify({
        error: "ANTHROPIC_API_KEY not configured",
      }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  let payload: IncomingPayload;
  try {
    payload = (await req.json()) as IncomingPayload;
  } catch {
    return new Response(JSON.stringify({ error: "invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const messages = (payload.messages ?? [])
    .filter((m) => m && (m.role === "user" || m.role === "assistant"))
    .map((m) => ({
      role: m.role,
      content: String(m.content ?? ""),
    }));

  if (messages.length === 0) {
    return new Response(JSON.stringify({ error: "messages array is empty" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const model = process.env.STACK_MODEL_ID ?? "claude-opus-4-7";
  const client = new Anthropic({ apiKey });

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();
      const send = (event: unknown) =>
        controller.enqueue(encoder.encode(sse(event)));

      try {
        const response = client.messages.stream({
          model,
          max_tokens: 4096,
          system: STACK_ANALYZER_SYSTEM_PROMPT,
          messages,
        });

        response.on("text", (chunk: string) => {
          send({ type: "delta", text: chunk });
        });
        response.on("error", (err: Error) => {
          send({ type: "error", message: err.message });
        });

        await response.finalMessage();
        send({ type: "done" });
      } catch (err) {
        const message = err instanceof Error ? err.message : "unknown error";
        send({ type: "error", message });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
