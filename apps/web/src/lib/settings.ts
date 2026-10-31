const KEY = "niyam.apiKey";
const ACTOR = "niyam.actor";
export const DEFAULT_ACTOR = "compliance.reviewer";
const listeners = new Set<() => void>();

function read(k: string): string {
  try {
    return localStorage.getItem(k) ?? "";
  } catch {
    return "";
  }
}
function write(k: string, v: string): void {
  try {
    if (v) localStorage.setItem(k, v);
    else localStorage.removeItem(k);
  } catch {
    /* storage unavailable: keep in memory for this tab only */
  }
}

let memoryKey: string | null = null;
let memoryActor: string | null = null;

export function getApiKey(): string {
  return read(KEY);
}
export function setApiKey(value: string): void {
  memoryKey = value;
  write(KEY, value);
  listeners.forEach((l) => l());
}
export function currentApiKey(): string {
  return memoryKey ?? getApiKey();
}

export function currentActor(): string {
  return memoryActor ?? (read(ACTOR) || "");
}
export function setActor(value: string): void {
  memoryActor = value;
  write(ACTOR, value);
  listeners.forEach((l) => l());
}

export function subscribeSettings(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** Headers sent on every request. The key is never logged. */
export function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  const key = currentApiKey();
  if (key) h["X-API-Key"] = key;
  const actor = currentActor().trim();
  if (actor) h["X-Actor"] = actor;
  return h;
}
