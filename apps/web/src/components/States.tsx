import * as React from "react";
import { AlertTriangle, KeyRound, SearchX, RotateCw } from "lucide-react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";
import { setApiKey } from "@/lib/settings";
import { cn } from "@/lib/utils";
import { useTour } from "@/components/Tour";

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
  if (unauthorized) return <UnlockPanel onRetry={onRetry} detail={message} />;
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <span className="text-[var(--taupe)]"><AlertTriangle size={22} strokeWidth={1.6} /></span>
      <p className="text-[14px] font-medium">{e?.status === 0 ? "Backend unreachable" : "Could not load this"}</p>
      <p className="max-w-[52ch] text-[12.5px] text-[var(--muted-foreground)]">{message}</p>
      {onRetry ? (
        <button type="button" className="btn btn-sm" onClick={onRetry}>
          <RotateCw size={13} /> Retry
        </button>
      ) : null}
    </div>
  );
}

function UnlockPanel({ onRetry, detail }: { onRetry?: () => void; detail: string }) {
  const qc = useQueryClient();
  const tour = useTour();
  const [key, setKey] = React.useState("");
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    setApiKey(key.trim());
    void qc.invalidateQueries();
    onRetry?.();
    tour.start();
  };
  return (
    <div role="alert" className="mx-auto flex max-w-[440px] flex-col items-center gap-3 px-6 py-8 text-center">
      <span className="text-[var(--taupe)]"><KeyRound size={22} strokeWidth={1.6} /></span>
      <p className="text-[16px] font-semibold tracking-[-0.01em]">Unlock this demo workspace</p>
      <p className="text-[13px] leading-relaxed text-[var(--muted-foreground)]">
        Paste the demo API key from the submission notes. It stays in this browser. Then we start a two-minute walkthrough of one stale sentence.
      </p>
      <p className="sr-only">{detail}</p>
      <form onSubmit={save} className="mt-1 flex w-full flex-col gap-2 text-left">
        <label htmlFor="unlock-key" className="label">Demo API key</label>
        <input
          id="unlock-key"
          className="field font-mono"
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder="Paste the key, then continue"
          required
        />
        <button type="submit" className="btn btn-primary mt-1">Unlock and start the walkthrough</button>
      </form>
      <div className="flex flex-wrap justify-center gap-2">
        <Link to="/guide" className="btn btn-sm">Read the dry run first</Link>
        <Link to="/settings" className="btn btn-sm">Open Settings</Link>
      </div>
    </div>
  );
}
