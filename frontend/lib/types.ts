export interface Citation {
  source: string;
  page: number | null;
  section: string | null;
  score: number | null;
  text: string;
}

export interface DocumentInfo {
  source: string;
  chunks: number;
  file_type: string | null;
}

export interface UploadResult {
  filename: string;
  status: "indexed" | "error";
  chunks: number;
  error: string | null;
}

export interface HealthInfo {
  status: string;
  llm_model: string;
  embed_model: string;
  rate_limit_mode: string;
}

export interface ConfigInfo {
  chunk_size: number;
  chunk_overlap: number;
  top_k: number;
  retrieval_mode: string;
  max_tokens: number;
  max_upload_mb: number;
  per_ip_query_limit: number;
}

export interface QuotaInfo {
  per_ip_limit: number;
  remaining: number;
  reset_seconds: number;
  global_daily_cap: number;
  global_used: number;
}

export interface QueryDone {
  latency_ms: number;
  chunks_retrieved: number;
  tokens: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    embedding_tokens: number;
  };
}

export interface RateLimitError {
  error: "rate_limited";
  scope: "ip" | "global";
  message: string;
  reset_seconds: number;
  remaining?: number;
}

export type UploadStatus = "queued" | "parsing" | "indexed" | "error";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  meta?: { latency_ms: number; chunks: number; tokens?: number };
  notFound?: boolean;
  streaming?: boolean;
}
