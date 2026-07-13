"use client";

import { useState } from "react";
import { Citation } from "@/lib/types";

function locationLabel(c: Citation): string {
  if (c.page != null) return `p. ${c.page}`;
  if (c.section) return c.section;
  return "";
}

function CitationRow({ c, index }: { c: Citation; index: number }) {
  const [open, setOpen] = useState(false);
  const loc = locationLabel(c);
  return (
    <div className="rounded-lg border border-ink-700 bg-ink-900/60 overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-ink-800/60 transition-colors"
      >
        <span className="text-xs font-mono text-accent shrink-0">[{index + 1}]</span>
        <span className="text-sm text-slate-200 truncate">{c.source}</span>
        {loc && (
          <span className="inline-flex items-center leading-none text-xs text-slate-400 shrink-0 rounded bg-ink-700 px-1.5 py-1">
            {loc}
          </span>
        )}
        {c.score != null && (
          <span className="ml-auto text-xs font-mono text-slate-500 shrink-0">
            {c.score.toFixed(3)}
          </span>
        )}
        <svg
          className={`w-4 h-4 text-slate-500 transition-transform shrink-0 ${open ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>
      {open && (
        <div className="px-3 py-2 border-t border-ink-700 bg-ink-950/50">
          <p className="text-xs text-slate-400 whitespace-pre-wrap leading-relaxed max-h-56 overflow-y-auto scroll-thin">
            {c.text}
          </p>
        </div>
      )}
    </div>
  );
}

export default function Citations({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState(false);
  if (!citations || citations.length === 0) return null;
  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500 font-medium hover:text-slate-300 transition-colors"
      >
        <svg
          className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
        </svg>
        Sources
        <span className="inline-flex items-center leading-none normal-case rounded-full bg-ink-700 text-slate-300 px-1.5 py-1 text-[11px]">
          {citations.length}
        </span>
        <span className="normal-case text-slate-600 font-normal">
          {open ? "" : "click to see the text"}
        </span>
      </button>
      {open && (
        <div className="mt-2 space-y-1.5">
          {citations.map((c, i) => (
            <CitationRow key={i} c={c} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
