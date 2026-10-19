import type {
  AiAnswer,
  AiStatus,
  AuditEvent,
  CaseSummary,
  EntityRecord,
  EventListResponse,
  Evidence,
  Finding,
  FindingListResponse,
  GraphResponse,
  HashVerifyResponse,
  Health,
  ParseResponse,
  ReportRecord,
  TimelineResponse,
} from "@/types";

export const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ?? "/api"
).replace(/\/+$/, "");

const ACCESS_TOKEN_KEY = "red-thread.accessToken";

export function accessGateRequired(): boolean {
  return import.meta.env.VITE_REQUIRE_ACCESS_TOKEN === "true";
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(ACCESS_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAccessToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
  } catch {
    // Session storage may be unavailable in private modes.
  }
}

export function clearAccessToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  } catch {
    // Ignore storage failures.
  }
}

function accessTokenParams(): Record<string, string> {
  const token = getAccessToken();
  return token ? { access_token: token } : {};
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  method?: string;
  caseId?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers ?? {}) };
  if (options.caseId) headers["X-Case-ID"] = options.caseId;
  const token = getAccessToken();
  if (token) headers["X-API-Key"] = token;

  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    headers,
    body,
    cache: "no-store",
  });

  if (!response.ok) {
    let detail: unknown = null;
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload;
      if (typeof payload?.detail === "string") message = payload.detail;
      else if (Array.isArray(payload?.detail)) {
        message = payload.detail
          .map((item: { msg?: string }) => item.msg ?? "Validation error")
          .join("; ");
      }
    } catch {
      // keep the status text
    }
    throw new ApiError(response.status, message, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const value = search.toString();
  return value ? `?${value}` : "";
}

export const api = {
  health: () => request<Health>("/health"),

  listCases: () => request<CaseSummary[]>("/cases"),
  getCase: (caseId: string) => request<CaseSummary>(`/cases/${caseId}`),
  createCase: (payload: { title: string; description?: string; investigator_notes?: string }) =>
    request<CaseSummary>("/cases", { method: "POST", body: payload }),
  updateCase: (
    caseId: string,
    payload: Partial<Pick<CaseSummary, "title" | "description" | "status" | "investigator_notes">>,
  ) => request<CaseSummary>(`/cases/${caseId}`, { method: "PATCH", body: payload }),

  listEvidence: (caseId: string) =>
    request<Evidence[]>(`/cases/${caseId}/evidence`, { caseId }),
  uploadEvidence: (caseId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Evidence>(`/cases/${caseId}/evidence`, {
      method: "POST",
      caseId,
      body: form,
    });
  },
  getEvidence: (caseId: string, evidenceId: string) =>
    request<Evidence>(`/evidence/${evidenceId}${query({ case_id: caseId })}`, { caseId }),
  verifyEvidence: (caseId: string, evidenceId: string) =>
    request<HashVerifyResponse>(
      `/evidence/${evidenceId}/verify${query({ case_id: caseId })}`,
      { method: "POST", caseId },
    ),
  parseEvidence: (caseId: string, evidenceId: string, reparse = false, parser?: string) =>
    request<ParseResponse>(
      `/evidence/${evidenceId}/parse${query({ case_id: caseId, reparse, parser })}`,
      { method: "POST", caseId },
    ),
  getEvidenceText: (caseId: string, evidenceId: string) =>
    request<{ text: string; truncated: boolean; size_bytes: number }>(
      `/evidence/${evidenceId}/text${query({ case_id: caseId })}`,
      { caseId },
    ),
  getEvidenceContentUrl: (caseId: string, evidenceId: string) =>
    `${API_BASE}/evidence/${evidenceId}/content${query({
      case_id: caseId,
      ...accessTokenParams(),
    })}`,

  listEvents: (
    caseId: string,
    params: {
      event_type?: string;
      evidence_id?: string;
      entity?: string;
      timestamp_confidence?: string;
      start?: string;
      end?: string;
      limit?: number;
      offset?: number;
    } = {},
  ) => request<EventListResponse>(`/cases/${caseId}/events${query(params)}`, { caseId }),
  timeline: (caseId: string, limit = 1000) =>
    request<TimelineResponse>(`/cases/${caseId}/timeline${query({ limit })}`, { caseId }),
  graph: (caseId: string, includeTemporal = false, limit = 500) =>
    request<GraphResponse>(
      `/cases/${caseId}/graph${query({ include_temporal: includeTemporal, limit })}`,
      { caseId },
    ),
  listEntities: (caseId: string, entityType?: string) =>
    request<EntityRecord[]>(
      `/cases/${caseId}/entities${query({ entity_type: entityType })}`,
      { caseId },
    ),

  listFindings: (
    caseId: string,
    params: { severity?: string; status?: string; category?: string } = {},
  ) => request<FindingListResponse>(`/cases/${caseId}/findings${query(params)}`, { caseId }),
  reviewFinding: (
    caseId: string,
    findingId: string,
    payload: { status: string; reviewer_note?: string },
  ) =>
    request<Finding>(`/findings/${findingId}/review${query({ case_id: caseId })}`, {
      method: "POST",
      caseId,
      body: payload,
    }),
  reconcile: (caseId: string) =>
    request<{ case_id: string; findings_created: number; findings: Finding[] }>(
      `/cases/${caseId}/reconcile`,
      { method: "POST", caseId },
    ),

  audit: (caseId: string) => request<AuditEvent[]>(`/cases/${caseId}/audit`, { caseId }),
  getAuthExportUrl: (caseId: string, format: "json" | "csv") =>
    `${API_BASE}/cases/${caseId}/auth/export${query({
      format,
      ...accessTokenParams(),
    })}`,

  aiStatus: () => request<AiStatus>("/ai/status"),
  askAi: (caseId: string, question: string) =>
    request<AiAnswer>(`/cases/${caseId}/ai/ask`, {
      method: "POST",
      caseId,
      body: { question },
    }),

  listReports: (caseId: string) => request<ReportRecord[]>(`/cases/${caseId}/reports`, { caseId }),
  generateReport: (caseId: string, reportType: "pdf" | "json") =>
    request<ReportRecord>(`/cases/${caseId}/reports`, {
      method: "POST",
      caseId,
      body: { report_type: reportType },
    }),
  getReportDownloadUrl: (caseId: string, reportId: string) =>
    `${API_BASE}/reports/${reportId}/download${query({
      case_id: caseId,
      ...accessTokenParams(),
    })}`,
};
