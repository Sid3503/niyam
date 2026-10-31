import { Tooltip } from "@base-ui/react/tooltip";

/** Shared delay so neighbouring hints open without a second wait. */
export function HintsProvider({ children }: { children: React.ReactNode }) {
  return (
    <Tooltip.Provider delay={200} closeDelay={80}>
      {children}
    </Tooltip.Provider>
  );
}

/**
 * Portal tooltip. Use this instead of native `title=` — tables clip overflow,
 * and the native tooltip is too easy to miss on chips.
 */
export function Hint({
  text,
  children,
  label,
}: {
  text?: string | null;
  children: React.ReactElement;
  /** Accessible name for the trigger when the visible text is a short chip. */
  label?: string;
}) {
  if (!text) return children;
  return (
    <Tooltip.Root>
      <Tooltip.Trigger delay={200} closeDelay={80} render={children} aria-label={label} />
      <Tooltip.Portal>
        <Tooltip.Positioner side="top" sideOffset={8} className="hint-positioner">
          <Tooltip.Popup className="hint-popup" data-testid="hint">
            {text}
          </Tooltip.Popup>
        </Tooltip.Positioner>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

/** A “?” next to a label. Use on stats, clock figures and table headers. */
export function HintLabel({ label, hint }: { label: string; hint: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      {label}
      <Hint text={hint} label={`What “${label}” means`}>
        <span className="hint-mark" data-hint-for={label}>
          ?
        </span>
      </Hint>
    </span>
  );
}
