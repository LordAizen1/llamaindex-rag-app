"use client";

import { QuotaInfo } from "@/lib/types";

export default function QuotaBadge({ quota }: { quota: QuotaInfo | null }) {
  if (!quota) return null;
  const low = quota.remaining <= 2;
  return (
    <div
      title={`${quota.per_ip_limit} queries per visitor, no reset. ${quota.global_used} of ${quota.global_daily_cap} used across everyone today.`}
      className={`inline-flex items-center justify-center leading-none text-xs rounded-full px-3 py-1.5 border ${
        low
          ? "border-amber-500/40 text-amber-300 bg-amber-500/10"
          : "border-ink-700 text-slate-400 bg-ink-900/60"
      }`}
    >
      {quota.remaining}/{quota.per_ip_limit} free queries left
    </div>
  );
}
