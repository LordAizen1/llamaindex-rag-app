"use client";

import { useCallback, useRef, useState } from "react";
import { uploadFiles } from "@/lib/api";
import { UploadStatus } from "@/lib/types";

interface FileState {
  name: string;
  status: UploadStatus;
  chunks?: number;
  error?: string;
}

const ACCEPT = ".pdf,.docx,.md,.markdown,.txt";
const ACCEPTED_EXT = ["pdf", "docx", "md", "markdown", "txt"];

export default function UploadPanel({ onIndexed }: { onIndexed: () => void }) {
  const [dragging, setDragging] = useState(false);
  const [files, setFiles] = useState<FileState[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    async (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;
      const picked = Array.from(fileList);

      const valid = picked.filter((f) =>
        ACCEPTED_EXT.includes(f.name.split(".").pop()?.toLowerCase() || "")
      );
      const invalid = picked.filter((f) => !valid.includes(f));

      setFiles((prev) => [
        ...prev,
        ...valid.map((f) => ({ name: f.name, status: "parsing" as UploadStatus })),
        ...invalid.map((f) => ({
          name: f.name,
          status: "error" as UploadStatus,
          error: "Unsupported file type",
        })),
      ]);

      if (valid.length === 0) return;

      try {
        const results = await uploadFiles(valid);
        setFiles((prev) =>
          prev.map((fs) => {
            const r = results.find((res) => res.filename === fs.name);
            if (!r) return fs;
            return r.status === "indexed"
              ? { ...fs, status: "indexed", chunks: r.chunks }
              : { ...fs, status: "error", error: r.error || "Failed to index" };
          })
        );
        onIndexed();
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Upload failed";
        setFiles((prev) =>
          prev.map((fs) =>
            fs.status === "parsing" ? { ...fs, status: "error", error: msg } : fs
          )
        );
      }
    },
    [onIndexed]
  );

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
          dragging
            ? "border-accent bg-accent/5"
            : "border-ink-700 hover:border-ink-600 bg-ink-900/40"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <p className="text-sm text-slate-300">
          <span className="text-accent font-medium">Drop files</span> or click to upload
        </p>
        <p className="text-xs text-slate-500 mt-1">PDF, DOCX, or Markdown · up to 20 MB each</p>
      </div>

      {files.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {files.map((f, i) => (
            <li
              key={i}
              className="flex items-center gap-2 text-sm rounded-lg border border-ink-700 bg-ink-900/50 px-3 py-2"
            >
              <StatusDot status={f.status} />
              <span className="truncate text-slate-200">{f.name}</span>
              <span className="ml-auto text-xs shrink-0">
                {f.status === "indexed" && (
                  <span className="text-emerald-400">{f.chunks} chunks</span>
                )}
                {f.status === "parsing" && <span className="text-slate-400">indexing…</span>}
                {f.status === "error" && (
                  <span className="text-rose-400" title={f.error}>
                    {f.error}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function StatusDot({ status }: { status: UploadStatus }) {
  const color =
    status === "indexed"
      ? "bg-emerald-400"
      : status === "error"
      ? "bg-rose-400"
      : "bg-amber-400 animate-pulse";
  return <span className={`w-2 h-2 rounded-full shrink-0 ${color}`} />;
}
