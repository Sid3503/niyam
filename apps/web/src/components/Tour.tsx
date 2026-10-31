import * as React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { X } from "lucide-react";
import { markTourSeen, TOUR_STEPS } from "@/lib/tour";

type TourApi = {
  active: boolean;
  index: number;
  start: () => void;
  stop: () => void;
  next: () => void;
  back: () => void;
};

const TourContext = React.createContext<TourApi | null>(null);

const NOOP: TourApi = { active: false, index: 0, start: () => {}, stop: () => {}, next: () => {}, back: () => {} };

export function useTour(): TourApi {
  return React.useContext(TourContext) ?? NOOP;
}

export function TourProvider({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const [index, setIndex] = React.useState<number | null>(null);

  const start = React.useCallback(() => {
    setIndex(0);
    navigate(TOUR_STEPS[0].path);
  }, [navigate]);

  const stop = React.useCallback(() => {
    markTourSeen();
    setIndex(null);
  }, []);

  const next = React.useCallback(() => {
    setIndex((i) => {
      if (i === null) return i;
      const n = i + 1;
      if (n >= TOUR_STEPS.length) {
        markTourSeen();
        return null;
      }
      navigate(TOUR_STEPS[n].path);
      return n;
    });
  }, [navigate]);

  const back = React.useCallback(() => {
    setIndex((i) => {
      if (i === null || i === 0) return i;
      const n = i - 1;
      navigate(TOUR_STEPS[n].path);
      return n;
    });
  }, [navigate]);

  const value = React.useMemo(
    () => ({ active: index !== null, index: index ?? 0, start, stop, next, back }),
    [index, start, stop, next, back],
  );

  return (
    <TourContext.Provider value={value}>
      {children}
      {index !== null ? <TourCard index={index} /> : null}
    </TourContext.Provider>
  );
}

function TourCard({ index }: { index: number }) {
  const { next, back, stop } = useTour();
  const { pathname } = useLocation();
  const step = TOUR_STEPS[index];
  const last = index === TOUR_STEPS.length - 1;
  const panel = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    panel.current?.focus();
  }, [index]);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") stop();
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") back();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, back, stop]);

  return (
    <div className="tour-scrim" role="presentation">
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        tabIndex={-1}
        className="tour-card"
      >
        <div className="flex items-start justify-between gap-3">
          <p className="label">
            Walkthrough {index + 1} of {TOUR_STEPS.length}
            {pathname !== step.path ? " · opening that page" : ""}
          </p>
          <button type="button" className="btn btn-sm" onClick={stop} aria-label="Close walkthrough">
            <X size={14} /> Skip
          </button>
        </div>
        <h2 id="tour-title" className="mt-3 text-[20px] font-semibold tracking-[-0.02em] leading-snug">
          {step.title}
        </h2>
        <p className="mt-2 text-[14px] leading-relaxed text-[var(--muted-foreground)]">{step.body}</p>
        <blockquote className="tour-ex mt-4">
          <span className="label">Example</span>
          <p className="mt-1.5 text-[13.5px] leading-relaxed">{step.example}</p>
        </blockquote>
        <div className="mt-5 flex items-center justify-between gap-3">
          <button type="button" className="btn btn-sm" onClick={back} disabled={index === 0}>
            Back
          </button>
          <button type="button" className="btn btn-primary" onClick={last ? stop : next}>
            {last ? "Done — send the approved copy" : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}
