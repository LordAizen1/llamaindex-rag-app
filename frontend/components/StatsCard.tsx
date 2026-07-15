"use client";

import { Cpu, Database, Files, MagnifyingGlass, Sparkle } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { getConfig, getHealth } from "@/lib/api";
import { ConfigInfo, DocumentInfo, HealthInfo } from "@/lib/types";

function Tile({ icon, value, label }: { icon: React.ReactNode; value: React.ReactNode; label: string }) {
  return (
    <div className="rounded-xl border border-ink-700 bg-ink-950/40 px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-slate-500 mb-1">
        {icon}
        <span className="text-[10px] uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-2xl font-semibold text-white leading-none">{value}</div>
    </div>
  );
}

function Row({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-slate-500 shrink-0">{icon}</span>
      <span className="text-slate-400 shrink-0">{label}</span>
      <span
        className="ml-auto font-mono text-[11px] text-slate-300 truncate max-w-[10rem]"
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

export default function StatsCard({ documents }: { documents: DocumentInfo[] }) {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [config, setConfig] = useState<ConfigInfo | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {});
    getConfig().then(setConfig).catch(() => {});
  }, []);

  const totalChunks = documents.reduce((sum, d) => sum + d.chunks, 0);

  return (
    <div className="rounded-2xl border border-ink-700 bg-ink-900/30 p-4">
      <h2 className="text-sm font-medium text-slate-200 mb-3">Under the hood</h2>

      <div className="grid grid-cols-2 gap-2 mb-3">
        <Tile icon={<Files size={14} weight="duotone" />} value={documents.length} label="Documents" />
        <Tile icon={<Database size={14} weight="duotone" />} value={totalChunks} label="Chunks" />
      </div>

      <div className="space-y-2 text-xs pt-1">
        <Row icon={<Cpu size={14} />} label="LLM" value={health?.llm_model ?? "…"} />
        <Row icon={<Sparkle size={14} />} label="Embeddings" value={health?.embed_model ?? "…"} />
        <Row icon={<Database size={14} />} label="Vector store" value="ChromaDB" />
        <Row
          icon={<MagnifyingGlass size={14} />}
          label="Retrieval"
          value={
            config
              ? `${config.retrieval_mode === "hybrid" ? "hybrid" : "vector"} · top-${config.top_k}`
              : "…"
          }
        />
      </div>
    </div>
  );
}
