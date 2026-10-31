import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { bboxToRect, pageAtOffset, scaleForZoom, stepZoom } from "@/components/workbench/geometry";
import { editsReducer, emptyEdits, isAppendEdit, toApplyEdits } from "@/components/workbench/pendingEdits";
import { ApplyError, StaleTextList, staleFromError } from "@/components/workbench/ApplyView";
import { ApiError } from "@/lib/api";
import { activeSentence, seekAndPlay, seekTarget, spanRuns } from "@/components/voice/audio";
import type { VoiceSentence } from "@/lib/types";

describe("bboxToRect", () => {
  it("scales PDF points (top-left origin) to css pixels", () => {
    expect(bboxToRect([72, 100, 172, 120], [612, 792], 2)).toEqual({ left: 144, top: 200, width: 200, height: 40 });
  });
  it("uses zoom scale and clamps to the page", () => {
    const s = scaleForZoom(1.5);
    expect(s).toBeCloseTo((96 / 72) * 1.5);
    const r = bboxToRect([-10, 780, 700, 900], [612, 792], 1)!;
    expect(r).toEqual({ left: 0, top: 780, width: 612, height: 12 });
  });
  it("normalises swapped corners and rejects degenerate boxes", () => {
    expect(bboxToRect([20, 30, 10, 10], [100, 100], 1)).toEqual({ left: 10, top: 10, width: 10, height: 20 });
    expect(bboxToRect([10, 10, 10, 30], [100, 100], 1)).toBeNull();
    expect(bboxToRect([0, 0, 5, 5], [100, 100], 0)).toBeNull();
  });
  it("steps zoom and finds the current page", () => {
    expect(stepZoom(1, 1)).toBe(1.25);
    expect(stepZoom(2, 1)).toBe(2);
    expect(stepZoom(0.5, -1)).toBe(0.5);
    expect(pageAtOffset([0, 800, 1600], 900)).toBe(2);
  });
});

describe("pending edits reducer", () => {
  it("toggles an edit on and off", () => {
    let s = editsReducer(emptyEdits, { type: "toggle", id: "a", wording: "T+5 days" });
    expect(s.order).toEqual(["a"]);
    s = editsReducer(s, { type: "set", id: "a", wording: "T+5 working days" });
    expect(toApplyEdits(s)).toEqual([{ finding_id: "a", wording: "T+5 working days" }]);
    s = editsReducer(s, { type: "toggle", id: "a", wording: "ignored" });
    expect(s).toEqual(emptyEdits);
  });
  it("keeps order, ignores set on unknown ids, drops blank wording, clears", () => {
    let s = editsReducer(emptyEdits, { type: "toggle", id: "a", wording: "one" });
    s = editsReducer(s, { type: "toggle", id: "b", wording: "two" });
    expect(editsReducer(s, { type: "set", id: "zzz", wording: "x" })).toBe(s);
    s = editsReducer(s, { type: "set", id: "a", wording: "   " });
    expect(toApplyEdits(s)).toEqual([{ finding_id: "b", wording: "two" }]);
    expect(editsReducer(s, { type: "remove", id: "a" }).order).toEqual(["b"]);
    expect(editsReducer(s, { type: "clear" })).toEqual(emptyEdits);
  });
  it("a finding without a box, or a missing one, applies as appended text", () => {
    expect(isAppendEdit({ status: "missing", bbox: [0, 0, 1, 1] })).toBe(true);
    expect(isAppendEdit({ status: "outdated", bbox: null })).toBe(true);
    expect(isAppendEdit({ status: "outdated", bbox: [0, 0, 1, 1] })).toBe(false);
  });
});

describe("stale text rendering", () => {
  it("lists every stale quote and says covering words is not a fix", () => {
    render(<StaleTextList items={[{ finding_id: "f1", quote: "assured returns of 12%" }, { finding_id: "f2", quote: "7 working days" }]} />);
    const box = screen.getByTestId("stale-text");
    expect(box.textContent).toContain("assured returns of 12%");
    expect(box.textContent).toContain("7 working days");
    expect(box.textContent).toMatch(/covering words is not a fix/i);
  });
  it("renders nothing for an empty list", () => {
    const { container } = render(<StaleTextList items={[]} />);
    expect(container.textContent).toBe("");
  });
  it("shows a 409 plainly and reads the stale list from the error body", () => {
    const err = new ApiError(409, "stale_text_remains", "Old wording is still extractable on page 2.");
    err.body = { error: { code: "stale_text_remains", message: "m", stale_text_remains: [{ finding_id: "f1", quote: "T+7" }] } };
    const stale = staleFromError(err);
    expect(stale).toEqual([{ finding_id: "f1", quote: "T+7" }]);
    render(<ApplyError error={err} stale={stale} />);
    expect(screen.getByTestId("apply-error").textContent).toMatch(/409, stale text remains/);
    expect(screen.getByTestId("apply-error").textContent).toContain("Nothing was saved");
    expect(screen.getByTestId("stale-text").textContent).toContain("T+7");
  });
  it("tolerates a 409 with no details", () => {
    expect(staleFromError(new ApiError(409, "stale_text_remains", "x"))).toEqual([]);
  });
});

describe("audio seek helper", () => {
  const sentences: VoiceSentence[] = [
    { idx: 0, start: 0, end: 4, text: "Hello.", start_char: 0, end_char: 6 },
    { idx: 1, start: 4, end: 9, text: "Returns are assured.", start_char: 7, end_char: 27 },
  ];
  it("seeks to audio_time[0], clamped to the duration", () => {
    expect(seekTarget({ audio_time: [4.5, 9] }, 30)).toBe(4.5);
    expect(seekTarget({ audio_time: [40, 45] }, 30)).toBe(30);
    expect(seekTarget({ audio_time: [-2, 1] }, 30)).toBe(0);
    expect(seekTarget({ audio_time: null }, 30)).toBeNull();
  });
  it("sets currentTime and plays; does nothing without timing", () => {
    const play = vi.fn(() => Promise.reject(new Error("autoplay blocked")));
    const a = { currentTime: 0, play };
    expect(seekAndPlay(a, { audio_time: [4, 9] }, 30)).toBe(4);
    expect(a.currentTime).toBe(4);
    expect(play).toHaveBeenCalledOnce();
    const b = { currentTime: 1, play: vi.fn() };
    expect(seekAndPlay(b, { audio_time: null }, 30)).toBeNull();
    expect(b.currentTime).toBe(1);
    expect(b.play).not.toHaveBeenCalled();
    expect(seekAndPlay(null, { audio_time: [1, 2] })).toBeNull();
  });
  it("finds the active sentence and highlights finding spans inside a sentence", () => {
    expect(activeSentence(sentences, 5)).toBe(1);
    expect(activeSentence(sentences, 99)).toBe(-1);
    const runs = spanRuns(sentences[1].text, 7, [{ span: [19, 26], id: "f" }]);
    expect(runs.map((r) => r.text).join("")).toBe(sentences[1].text);
    expect(runs.find((r) => r.id === "f")?.text).toBe("assured");
  });
});
