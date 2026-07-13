import {
  Citation,
  ConfigInfo,
  DocumentInfo,
  HealthInfo,
  QuotaInfo,
  QueryDone,
  RateLimitError,
  UploadResult,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getDocuments(): Promise<DocumentInfo[]> {
  const r = await fetch(`${API}/api/documents`);
  if (!r.ok) throw new Error("Failed to load documents");
  return r.json();
}

export async function getHealth(): Promise<HealthInfo> {
  const r = await fetch(`${API}/api/health`);
  if (!r.ok) throw new Error("Failed to load health");
  return r.json();
}

export async function getConfig(): Promise<ConfigInfo> {
  const r = await fetch(`${API}/api/config`);
  if (!r.ok) throw new Error("Failed to load config");
  return r.json();
}

export async function getQuota(): Promise<QuotaInfo> {
  const r = await fetch(`${API}/api/quota`);
  if (!r.ok) throw new Error("Failed to load quota");
  return r.json();
}

export async function uploadFiles(files: File[]): Promise<UploadResult[]> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const r = await fetch(`${API}/api/upload`, { method: "POST", body: form });
  if (r.status === 429) {
    const body = await r.json();
    const mins = Math.ceil((body.reset_seconds ?? 3600) / 60);
    throw new Error(`${body.message} Resets in about ${mins} min.`);
  }
  if (!r.ok) throw new Error("Upload failed");
  return r.json();
}

export async function deleteDocument(source: string): Promise<void> {
  const r = await fetch(`${API}/api/documents/${encodeURIComponent(source)}`, {
    method: "DELETE",
  });
  if (!r.ok) throw new Error("Delete failed");
}

export async function reindexDocument(source: string): Promise<void> {
  const r = await fetch(
    `${API}/api/documents/${encodeURIComponent(source)}/reindex`,
    { method: "POST" }
  );
  if (!r.ok) throw new Error("Reindex failed");
}

export interface StreamHandlers {
  onMeta: (citations: Citation[], chunks: number, quotaRemaining: number) => void;
  onToken: (t: string) => void;
  onDone: (done: QueryDone) => void;
  onError: (message: string) => void;
  onRateLimit: (err: RateLimitError) => void;
}

/**
 * POST /api/query and parse the Server-Sent Events stream.
 * Handles a 429 (rate limit) as a non-streaming JSON response.
 */
export async function streamQuery(
  question: string,
  handlers: StreamHandlers,
  topK?: number
): Promise<void> {
  const r = await fetch(`${API}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK }),
  });

  if (r.status === 429) {
    handlers.onRateLimit((await r.json()) as RateLimitError);
    return;
  }
  if (!r.ok || !r.body) {
    handlers.onError(`Request failed (${r.status}).`);
    return;
  }

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      dispatchFrame(frame, handlers);
    }
  }
}

function dispatchFrame(frame: string, handlers: StreamHandlers): void {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;

  let data: any;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    return;
  }

  switch (event) {
    case "meta":
      handlers.onMeta(data.citations, data.chunks_retrieved, data.quota_remaining);
      break;
    case "token":
      handlers.onToken(data.t);
      break;
    case "done":
      handlers.onDone(data as QueryDone);
      break;
    case "error":
      handlers.onError(data.message);
      break;
  }
}
