import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { authHeaders, currentApiKey } from "./settings";
import type {
  ApplyEdit,
  ApplyResult,
  Approval,
  ApprovalKind,
  ApprovalStatus,
  CircularBody,
  CircularResult,
  CompareResult,
  Decision,
  DocumentDetail,
  Document,
  EvidenceListItem,
  EvidenceRecord,
  Impact,
  ImpactListItem,
  Overview,
  ProductFact,
  RetestResult,
  RuleDetail,
  RuleSummary,
  ScanResult,
  UploadBody,
  VoiceSample,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  /** Parsed JSON error body when the server sent one (e.g. stale_text_remains details). */
  body?: unknown;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type Params = Record<string, string | number | undefined | null>;

function qs(params?: Params): string {
  if (!params) return "";
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
  }
  const s = u.toString();
  return s ? `?${s}` : "";
}

async function send(method: "GET" | "POST", path: string, opts: { params?: Params; body?: unknown; accept?: string } = {}): Promise<Response> {
  const headers: Record<string, string> = { Accept: opts.accept ?? "application/json", ...authHeaders() };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}${qs(opts.params)}`, {
      method,
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network", "Cannot reach the Niyam API. Is the backend running?");
  }
  if (!res.ok) {
    let code = `http_${res.status}`;
    let message = res.statusText || "Request failed";
    let errBody: unknown;
    try {
      const j = await res.json();
      errBody = j;
      if (j?.error?.message) {
        code = j.error.code ?? code;
        message = j.error.message;
      }
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 401 && message === (res.statusText || "Request failed")) message = "An API key is required or the key is invalid.";
    const err = new ApiError(res.status, code, message);
    err.body = errBody;
    throw err;
  }
  return res;
}

async function request<T>(method: "GET" | "POST", path: string, opts: { params?: Params; body?: unknown } = {}): Promise<T> {
  const res = await send(method, path, opts);
  return (await res.json()) as T;
}

const enc = encodeURIComponent;

export const api = {
  overview: () => request<Overview>("GET", "/overview"),
  library: () => request<Document[]>("GET", "/library"),
  scan: () => request<ScanResult>("POST", "/library/scan", { body: {} }),
  upload: (body: UploadBody) => request<DocumentDetail>("POST", "/library/upload", { body }),
  doc: (id: string) => request<DocumentDetail>("GET", `/documents/${enc(id)}`),
  retest: (id: string, content?: string) =>
    request<RetestResult>("POST", `/documents/${enc(id)}/retest`, { body: content !== undefined ? { content } : {} }),
  sendForApproval: (findingId: string) => request<Approval>("POST", `/findings/${enc(findingId)}/send-for-approval`, { body: {} }),
  rules: () => request<RuleSummary[]>("GET", "/rules"),
  rule: (id: string) => request<RuleDetail>("GET", `/rules/${enc(id)}`),
  facts: () => request<ProductFact[]>("GET", "/product-facts"),
  extractText: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    let res: Response;
    try {
      res = await fetch(`${BASE}/extract-text`, { method: "POST", headers: { Accept: "application/json", ...authHeaders() }, body: fd });
    } catch {
      throw new ApiError(0, "network", "Cannot reach the Niyam API. Is the backend running?");
    }
    const j = await res.json().catch(() => null);
    if (!res.ok) throw new ApiError(res.status, j?.error?.code ?? `http_${res.status}`, j?.error?.message ?? "Could not read that file.");
    return j as { filename: string; chars: number; pages: number | null; text: string; truncated: boolean };
  },
  circular: (body: CircularBody) => request<CircularResult>("POST", "/circulars", { body }),
  approvals: (p: { status?: string; kind?: string }) => request<Approval[]>("GET", "/approvals", { params: p }),
  decide: (id: string, decision: Decision, reason?: string) =>
    request<Approval>("POST", `/approvals/${enc(id)}/decision`, { body: reason ? { decision, reason } : { decision } }),
  impactList: () => request<ImpactListItem[]>("GET", "/impact"),
  impact: (ruleId: string, version?: number) => request<Impact>("GET", `/impact/${enc(ruleId)}`, { params: { version } }),
  evidenceList: () => request<EvidenceListItem[]>("GET", "/evidence"),
  evidence: (id: string) => request<EvidenceRecord>("GET", `/evidence/${enc(id)}`),
  /** Fetched with headers (X-API-Key may be needed) and returned as text for a Blob download. */
  /** v0.3: multipart upload of a PDF or audio file (or a recorded blob). Returns DocumentDetail. */
  uploadFile: async (f: { file: Blob; filename: string; doc_type: string; product: string; owner: string; merchant?: string; title?: string }) => {
    const fd = new FormData();
    fd.append("file", f.file, f.filename);
    fd.append("doc_type", f.doc_type);
    fd.append("product", f.product);
    fd.append("owner", f.owner);
    if (f.merchant) fd.append("merchant", f.merchant);
    if (f.title) fd.append("title", f.title);
    let res: Response;
    try {
      res = await fetch(`${BASE}/library/upload-file`, { method: "POST", headers: { Accept: "application/json", ...authHeaders() }, body: fd });
    } catch {
      throw new ApiError(0, "network", "Cannot reach the Niyam API. Is the backend running?");
    }
    const j = await res.json().catch(() => null);
    if (!res.ok) throw new ApiError(res.status, j?.error?.code ?? `http_${res.status}`, j?.error?.message ?? "Could not upload that file.");
    return j as DocumentDetail;
  },
  voiceSamples: () => request<VoiceSample[]>("GET", "/voice/samples"),
  checkVoiceSample: (name: string) => request<DocumentDetail>("POST", `/voice/samples/${enc(name)}/check`, { body: {} }),
  docVersion: (id: string, versionId: string) => request<DocumentDetail>("GET", `/documents/${enc(id)}`, { params: { version_id: versionId } }),
  apply: (id: string, edits: ApplyEdit[], commit: boolean) => request<ApplyResult>("POST", `/documents/${enc(id)}/apply`, { body: { edits, commit } }),
  compare: (id: string, from: string, to: string) => request<CompareResult>("GET", `/documents/${enc(id)}/compare`, { params: { from, to } }),
  /** Authenticated binary fetch (PDF, audio, page image) returned as a Blob. `url` may be an absolute API path as given by the server. */
  blob: async (url: string): Promise<Blob> => {
    let res: Response;
    try {
      res = await fetch(url.startsWith("/api/") ? url : `${BASE}${url.startsWith("/") ? "" : "/"}${url}`, { headers: authHeaders() });
    } catch {
      throw new ApiError(0, "network", "Cannot reach the Niyam API. Is the backend running?");
    }
    if (!res.ok) {
      const j = await res.json().catch(() => null);
      throw new ApiError(res.status, j?.error?.code ?? `http_${res.status}`, j?.error?.message ?? "Could not fetch that file.");
    }
    return res.blob();
  },
  evidencePack: async (id: string) => (await send("GET", `/evidence/${enc(id)}/pack.pdf`, { accept: "application/pdf" })).blob(),
  evidenceExport: async (id: string) => (await send("GET", `/evidence/${enc(id)}/export`, { accept: "text/markdown" })).text(),
};

/** Query keys carry the api key so changing it in Settings refetches everything. */
const k = () => currentApiKey();
export const useOverview = () => useQuery({ queryKey: ["overview", k()], queryFn: api.overview });
export const useLibrary = () => useQuery({ queryKey: ["library", k()], queryFn: api.library });
export const useDoc = (id: string | null) => useQuery({ queryKey: ["document", id, k()], queryFn: () => api.doc(id as string), enabled: !!id });
export const useRules = () => useQuery({ queryKey: ["rules", k()], queryFn: api.rules });
export const useRule = (id: string | null) => useQuery({ queryKey: ["rule", id, k()], queryFn: () => api.rule(id as string), enabled: !!id });
export const useFacts = (enabled = true) => useQuery({ queryKey: ["facts", k()], queryFn: api.facts, enabled });
export const useApprovals = (p: { status?: ApprovalStatus | ""; kind?: ApprovalKind | "" }) =>
  useQuery({ queryKey: ["approvals", p, k()], queryFn: () => api.approvals(p) });
export const useImpactList = () => useQuery({ queryKey: ["impact-list", k()], queryFn: api.impactList });
export const useImpact = (ruleId: string | null, version?: number) =>
  useQuery({ queryKey: ["impact", ruleId, version ?? null, k()], queryFn: () => api.impact(ruleId as string, version), enabled: !!ruleId });
export const useVoiceSamples = (enabled = true) => useQuery({ queryKey: ["voice-samples", k()], queryFn: api.voiceSamples, enabled, retry: false });
export const useEvidenceList = () => useQuery({ queryKey: ["evidence-list", k()], queryFn: api.evidenceList });
export const useEvidence = (id: string | null) => useQuery({ queryKey: ["evidence", id, k()], queryFn: () => api.evidence(id as string), enabled: !!id });

function invalidate(qc: QueryClient, keys: string[]) {
  for (const key of keys) void qc.invalidateQueries({ queryKey: [key] });
}

const REVIEW_KEYS = ["overview", "library", "document", "evidence-list", "evidence", "impact", "impact-list"];

export function useScan() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.scan, onSuccess: () => invalidate(qc, REVIEW_KEYS) });
}
export function useUpload() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.upload, onSuccess: () => invalidate(qc, REVIEW_KEYS) });
}
export function useRetest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; content?: string }) => api.retest(v.id, v.content),
    onSuccess: () => invalidate(qc, REVIEW_KEYS),
  });
}
export function useSendForApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.sendForApproval,
    onSuccess: () => invalidate(qc, ["overview", "document", "approvals", "evidence", "evidence-list"]),
  });
}
export function useDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; decision: Decision; reason?: string }) => api.decide(v.id, v.decision, v.reason),
    onSuccess: () => invalidate(qc, ["approvals", "rules", "rule", "overview", "impact", "impact-list", "library", "document", "evidence", "evidence-list"]),
  });
}
export function useCreateCircular() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.circular, onSuccess: () => invalidate(qc, ["approvals", "rules", "overview", "impact-list"]) });
}
export function useUploadFile() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.uploadFile, onSuccess: () => invalidate(qc, REVIEW_KEYS) });
}
export function useCheckVoiceSample() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.checkVoiceSample, onSuccess: () => invalidate(qc, REVIEW_KEYS) });
}
