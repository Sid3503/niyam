import { Info, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";

export function Notice({ tone = "neutral", children, className }: { tone?: "warn" | "neutral"; children: React.ReactNode; className?: string }) {
  const Icon = tone === "warn" ? TriangleAlert : Info;
  return (
    <p
      role="note"
      className={cn(
        "flex gap-2 rounded-lg border px-3 py-2 text-[12.5px] leading-relaxed",
        tone === "warn" ? "border-[var(--warn-line)] bg-[var(--warn-bg)] text-[var(--warn-ink)]" : "border-[var(--border)] bg-[var(--card)] text-[var(--muted-foreground)]",
        className,
      )}
    >
      <Icon size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </p>
  );
}
