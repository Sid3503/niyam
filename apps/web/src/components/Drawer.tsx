import * as React from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/** Right-hand drawer. Esc and scrim click close it; focus is moved in, trapped, and restored on close. */
export function Drawer({ open, onClose, eyebrow, label, children }: { open: boolean; onClose: () => void; eyebrow: string; label: string; children: React.ReactNode }) {
  const panel = React.useRef<HTMLDivElement>(null);
  const closeBtn = React.useRef<HTMLButtonElement>(null);
  const titleId = React.useId();

  React.useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !panel.current) return;
      const els = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (!els.length) return;
      const first = els[0];
      const last = els[els.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      prev?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="drawer-scrim absolute inset-0 bg-[rgba(28,27,26,0.32)]" onClick={onClose} aria-hidden="true" />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="drawer-panel relative flex h-full w-full max-w-[680px] flex-col border-l border-[var(--border)] bg-[var(--card)] shadow-[0_0_40px_-12px_rgba(28,27,26,0.3)]"
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-3.5 sm:px-6">
          <span id={titleId} className="label">
            {eyebrow}
            <span className="sr-only"> — {label}</span>
          </span>
          <button ref={closeBtn} type="button" className="btn btn-sm !border-transparent" onClick={onClose} aria-label="Close (Esc)">
            <X size={16} />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
