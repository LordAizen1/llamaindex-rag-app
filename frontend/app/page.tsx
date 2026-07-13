"use client";

import { FileMagnifyingGlass, GithubLogo } from "@phosphor-icons/react";
import { useCallback, useEffect, useRef, useState } from "react";
import Chat, { ChatHandle } from "@/components/Chat";
import DocumentList from "@/components/DocumentList";
import ExampleQuestions from "@/components/ExampleQuestions";
import HowItWorks from "@/components/HowItWorks";
import QuotaBadge from "@/components/QuotaBadge";
import StatsCard from "@/components/StatsCard";
import UploadPanel from "@/components/UploadPanel";
import { getDocuments, getQuota } from "@/lib/api";
import { DocumentInfo, QuotaInfo } from "@/lib/types";

export default function Home() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [quota, setQuota] = useState<QuotaInfo | null>(null);
  const chatRef = useRef<ChatHandle>(null);

  const refreshDocs = useCallback(() => {
    getDocuments().then(setDocuments).catch(() => {});
  }, []);
  const refreshQuota = useCallback(() => {
    getQuota().then(setQuota).catch(() => {});
  }, []);

  useEffect(() => {
    refreshDocs();
    refreshQuota();
  }, [refreshDocs, refreshQuota]);

  return (
    <main className="min-h-screen max-w-6xl mx-auto px-4 py-6 sm:py-10">
      <header className="flex flex-wrap items-center gap-3 mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent/25 to-accent-soft/10 border border-accent/40 grid place-items-center text-accent shadow-lg shadow-accent-soft/10">
            <FileMagnifyingGlass size={22} weight="duotone" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white leading-tight">RAG Document Q&amp;A</h1>
            <p className="text-xs text-slate-500">
              Upload your docs, ask questions, and see the sources behind every answer
            </p>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <QuotaBadge quota={quota} />
          <a
            href={process.env.NEXT_PUBLIC_GITHUB_URL || "#"}
            target="_blank"
            rel="noreferrer"
            title="View source on GitHub"
            className="grid place-items-center w-8 h-8 rounded-lg border border-ink-700 text-slate-400 hover:text-white hover:border-accent/50 transition-colors"
          >
            <GithubLogo size={18} weight="fill" />
          </a>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_22rem] gap-5">
        {/* Chat column */}
        <section className="order-2 lg:order-1 flex flex-col">
          <div className="rounded-2xl border border-ink-700 bg-ink-900/30 p-4 h-[28rem] sm:h-[34rem] flex flex-col">
            <Chat ref={chatRef} onAfterQuery={refreshQuota} />
          </div>

          <div className="mt-4">
            <p className="text-xs uppercase tracking-wide text-slate-500 mb-2">Try an example</p>
            <ExampleQuestions onPick={(q) => chatRef.current?.ask(q)} />
          </div>

          <div className="mt-4">
            <HowItWorks />
          </div>
        </section>

        {/* Sidebar column */}
        <aside className="order-1 lg:order-2 flex flex-col gap-5 lg:h-[59rem]">
          <div className="rounded-2xl border border-ink-700 bg-ink-900/30 p-4 shrink-0">
            <h2 className="text-sm font-medium text-slate-200 mb-3">Add documents</h2>
            <UploadPanel onIndexed={refreshDocs} />
          </div>

          <div className="rounded-2xl border border-ink-700 bg-ink-900/30 p-4 flex flex-col lg:flex-1 lg:min-h-0">
            <div className="flex items-center justify-between mb-3 shrink-0">
              <h2 className="text-sm font-medium text-slate-200">Indexed documents</h2>
              {/* <span className="text-xs text-slate-500">{documents.length}</span> */}
            </div>
            <div className="h-64 lg:h-auto lg:flex-1 lg:min-h-0 overflow-y-auto scroll-thin -mr-1 pr-1">
              <DocumentList documents={documents} onChange={refreshDocs} />
            </div>
          </div>

          <StatsCard documents={documents} />
        </aside>
      </div>
    </main>
  );
}
