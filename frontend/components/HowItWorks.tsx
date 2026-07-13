"use client";

export default function HowItWorks() {
  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-4 text-sm text-slate-400 leading-relaxed">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-slate-200 font-medium">How this works</h3>
      </div>
      <p>
        When you upload a file, it gets split into small chunks and turned into embeddings with{" "}
        <span className="text-slate-300">text-embedding-3-large</span>, then saved in{" "}
        <span className="text-slate-300">ChromaDB</span>. When you ask something, it grabs the
        chunks that match best and sends them to <span className="text-slate-300">gpt-4.1-mini</span>,
        which only answers from those chunks. If the answer isn&apos;t in your files it says so
        instead of guessing, and you can always check the exact text it used.
      </p>
      <p className="mt-2 text-xs text-slate-500">
        Built with FastAPI, LlamaIndex, ChromaDB, OpenAI, Upstash Redis, Next.js, Tailwind, and Railway.
      </p>
    </div>
  );
}
