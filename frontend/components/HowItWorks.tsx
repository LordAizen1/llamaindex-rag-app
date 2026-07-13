"use client";

const GITHUB = process.env.NEXT_PUBLIC_GITHUB_URL || "#";

export default function HowItWorks() {
  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900/40 p-4 text-sm text-slate-400 leading-relaxed">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-slate-200 font-medium">How this works</h3>
        <a
          href={GITHUB}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-accent hover:underline"
        >
          GitHub ↗
        </a>
      </div>
      <p>
        Documents are parsed, split into overlapping chunks, embedded with{" "}
        <span className="text-slate-300">OpenAI text-embedding-3-large</span>, and stored in{" "}
        <span className="text-slate-300">ChromaDB</span>. Each question retrieves the most relevant
        chunks, which are passed to <span className="text-slate-300">gpt-4.1-mini</span> with an
        instruction to answer <em>only</em> from that context — and to say so when the answer
        isn&apos;t there. Every answer shows its sources so retrieval is visible, not a black box.
      </p>
      <p className="mt-2 text-xs text-slate-500">
        Stack: FastAPI · LlamaIndex · ChromaDB · OpenAI · Upstash Redis · Next.js · Tailwind · Railway
      </p>
    </div>
  );
}
