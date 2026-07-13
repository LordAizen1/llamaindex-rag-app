"use client";

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { streamQuery } from "@/lib/api";
import { ChatMessage } from "@/lib/types";
import Citations from "./Citations";

export interface ChatHandle {
  ask: (question: string) => void;
}

let idCounter = 0;
const nextId = () => `m${++idCounter}`;

const NOT_FOUND = "I couldn't find that in the provided documents.";

const Chat = forwardRef<ChatHandle, { onAfterQuery: () => void }>(
  ({ onAfterQuery }, ref) => {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [busy, setBusy] = useState(false);
    const [banner, setBanner] = useState<string | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, [messages]);

    const patch = (id: string, fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));

    const ask = async (question: string) => {
      const q = question.trim();
      if (!q || busy) return;
      setBanner(null);
      setBusy(true);

      const userMsg: ChatMessage = { id: nextId(), role: "user", content: q };
      const asstId = nextId();
      const asstMsg: ChatMessage = {
        id: asstId,
        role: "assistant",
        content: "",
        streaming: true,
      };
      setMessages((prev) => [...prev, userMsg, asstMsg]);

      await streamQuery(q, {
        onMeta: (citations, chunks) =>
          patch(asstId, (m) => ({ ...m, citations, meta: { ...(m.meta || { latency_ms: 0, chunks }), chunks } })),
        onToken: (t) => patch(asstId, (m) => ({ ...m, content: m.content + t })),
        onDone: (done) =>
          patch(asstId, (m) => ({
            ...m,
            streaming: false,
            notFound: m.content.trim().startsWith(NOT_FOUND),
            meta: {
              latency_ms: done.latency_ms,
              chunks: done.chunks_retrieved,
              tokens: done.tokens.total_tokens,
            },
          })),
        onError: (message) =>
          patch(asstId, (m) => ({
            ...m,
            streaming: false,
            content: m.content || `⚠ ${message}`,
          })),
        onRateLimit: (err) => {
          let msg = err.message;
          if (err.reset_seconds && err.reset_seconds > 0) {
            const mins = Math.ceil(err.reset_seconds / 60);
            msg += ` Try again in about ${mins} minute${mins === 1 ? "" : "s"}.`;
          }
          setBanner(msg);
          setMessages((prev) => prev.filter((m) => m.id !== asstId && m.id !== userMsg.id));
        },
      });

      setBusy(false);
      onAfterQuery();
    };

    useImperativeHandle(ref, () => ({ ask }));

    return (
      <div className="flex flex-col h-full">
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto scroll-thin space-y-4 pr-1"
        >
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center px-6">
              <div className="w-12 h-12 rounded-2xl bg-accent-soft/10 border border-accent/30 grid place-items-center text-accent mb-3">
                <svg viewBox="0 0 24 24" className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h8M8 14h5m-9 6l2.5-2.5A2 2 0 016.9 17H18a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v14z" />
                </svg>
              </div>
              <p className="text-slate-300 text-sm font-medium">Ask a question about your documents</p>
              <p className="text-slate-500 text-xs mt-1 max-w-xs">
                Answers come only from what&apos;s indexed — every one shows its sources, and it says
                so when the answer isn&apos;t there.
              </p>
            </div>
          )}
          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="flex justify-end">
                <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-accent-soft/20 border border-accent/30 px-4 py-2 text-slate-100">
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={m.id} className="flex justify-start">
                <div className="max-w-[75%] w-full">
                  <div
                    className={`rounded-2xl rounded-bl-sm border px-4 py-3 ${
                      m.notFound
                        ? "border-amber-500/30 bg-amber-500/5 text-amber-200"
                        : "border-ink-700 bg-ink-800/60 text-slate-200"
                    }`}
                  >
                    <span className={`whitespace-pre-wrap ${m.streaming ? "cursor-blink" : ""}`}>
                      {m.content}
                    </span>
                    {m.meta && !m.streaming && (
                      <div className="mt-2 text-xs text-slate-500">
                        {m.meta.chunks} chunk{m.meta.chunks === 1 ? "" : "s"} · {m.meta.latency_ms.toFixed(0)} ms
                        {m.meta.tokens ? ` · ${m.meta.tokens} tokens` : ""}
                      </div>
                    )}
                  </div>
                  {!m.notFound && m.citations && <Citations citations={m.citations} />}
                </div>
              </div>
            )
          )}
        </div>

        {banner && (
          <div className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 text-amber-200 text-sm px-4 py-2">
            {banner}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
            setInput("");
          }}
          className="mt-3 flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question…"
            disabled={busy}
            className="flex-1 rounded-xl bg-ink-900 border border-ink-700 px-4 py-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-accent/60 disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="rounded-xl bg-accent-soft px-5 py-3 font-medium text-white hover:bg-accent disabled:opacity-40 transition-colors"
          >
            {busy ? "…" : "Ask"}
          </button>
        </form>
      </div>
    );
  }
);

Chat.displayName = "Chat";
export default Chat;
