import type { ApplyEdit, Finding } from "@/lib/types";

/** Pending wording edits keyed by finding id. `order` keeps the order they were added in. */
export interface PendingEdits {
  order: string[];
  wording: Record<string, string>;
}
export const emptyEdits: PendingEdits = { order: [], wording: {} };

export type EditAction =
  | { type: "toggle"; id: string; wording: string }
  | { type: "set"; id: string; wording: string }
  | { type: "remove"; id: string }
  | { type: "clear" };

export function editsReducer(s: PendingEdits, a: EditAction): PendingEdits {
  switch (a.type) {
    case "toggle": {
      if (a.id in s.wording) return editsReducer(s, { type: "remove", id: a.id });
      return { order: [...s.order, a.id], wording: { ...s.wording, [a.id]: a.wording } };
    }
    case "set":
      if (!(a.id in s.wording)) return s;
      return { ...s, wording: { ...s.wording, [a.id]: a.wording } };
    case "remove": {
      if (!(a.id in s.wording)) return s;
      const { [a.id]: _gone, ...rest } = s.wording;
      return { order: s.order.filter((x) => x !== a.id), wording: rest };
    }
    case "clear":
      return emptyEdits;
  }
}

/** Request body edits. Blank wording is dropped: an empty edit would delete text, which is not a fix. */
export function toApplyEdits(s: PendingEdits): ApplyEdit[] {
  return s.order.filter((id) => (s.wording[id] ?? "").trim()).map((id) => ({ finding_id: id, wording: s.wording[id].trim() }));
}

/** A finding with no box on any page (missing disclosure) is applied as appended text, not an in-place rewrite. */
export function isAppendEdit(f: Pick<Finding, "status" | "bbox">): boolean {
  return f.status === "missing" || !f.bbox;
}
