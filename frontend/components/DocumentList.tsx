"use client";

import { useState } from "react";
import { deleteDocument, reindexDocument } from "@/lib/api";
import { DocumentInfo } from "@/lib/types";

export default function DocumentList({
  documents,
  onChange,
}: {
  documents: DocumentInfo[];
  onChange: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);

  const act = async (source: string, fn: () => Promise<void>) => {
    setBusy(source);
    try {
      await fn();
      onChange();
    } finally {
      setBusy(null);
    }
  };

  if (documents.length === 0) {
    return (
      <p className="text-sm text-slate-500 py-4 text-center">
        No documents indexed yet.
      </p>
    );
  }

  return (
    <ul className="space-y-1.5">
      {documents.map((d) => (
        <li
          key={d.source}
          className="rounded-lg border border-ink-700 bg-ink-900/50 px-3 py-2"
        >
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-[10px] font-mono uppercase text-accent/80 shrink-0 rounded bg-accent-soft/10 border border-accent/20 px-1.5 py-0.5">
              {d.file_type || "?"}
            </span>
            <span className="truncate text-sm text-slate-200" title={d.source}>
              {d.source}
            </span>
            <span className="ml-auto text-xs text-slate-500 shrink-0">{d.chunks} chunks</span>
          </div>
          <div className="flex justify-end gap-1 mt-2">
            <button
              onClick={() => act(d.source, () => reindexDocument(d.source))}
              disabled={busy === d.source}
              className="text-xs px-2 py-1 rounded border border-ink-700 text-slate-400 hover:text-white hover:border-accent/50 disabled:opacity-40"
            >
              {busy === d.source ? "…" : "Re-index"}
            </button>
            <button
              onClick={() => act(d.source, () => deleteDocument(d.source))}
              disabled={busy === d.source}
              className="text-xs px-2 py-1 rounded border border-ink-700 text-rose-400 hover:border-rose-500/50 disabled:opacity-40"
            >
              Delete
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
