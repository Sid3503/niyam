import { AlertTriangle, KeyRound, SearchX, RotateCw } from "lucide-react";
import { Link } from "react-router-dom";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton h-4", className)} aria-hidden="true" />;
}

export function LoadingBlock({ rows = 5, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3 p-5">
      <span className="sr-only">{label}…</span>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={i % 3 === 2 ? "w-2/3" : "w-full"} />
      ))}
    </div>
  );
}

export function EmptyState({ title, hint, icon }: { title: string; hint?: string; icon?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
      <span className="text-[var(--taupe)]">{icon ?? <SearchX size={22} strokeWidth={1.6} />}</span>
      <p className="text-[14px] font-medium">{title}</p>
      {hint ? <p className="max-w-[46ch] text-[12.5px] text-[var(--muted-foreground)]">{hint}</p> : null}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  const unauthorized = e?.status === 401;
  const message = e?.message ?? (error instanceof Error ? error.message : "Something went wrong.");
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <span className="text-[var(--taupe)]">{unauthorized ? <KeyRound size={22} strokeWidth={1.6} /> : <AlertTriangle size={22} strokeWidth={1.6} />}</span>
      <p className="text-[14px] font-medium">{unauthorized ? "Not authorised (401)" : e?.status === 0 ? "Backend unreachable" : "Could not load this"}</p>
      <p className="max-w-[52ch] text-[12.5px] text-[var(--muted-foreground)]">{message}</p>
      <div className="flex gap-2">
        {unauthorized ? <Link to="/settings" className="btn btn-primary btn-sm">Open Settings</Link> : null}
        {onRetry ? (
          <button type="button" className="btn btn-sm" onClick={onRetry}>
            <RotateCw size={13} /> Retry
          </button>
        ) : null}
      </div>
    </div>
  );
}
