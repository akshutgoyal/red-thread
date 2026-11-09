import type {
  AiAnswer,
  AiStatus,
  AiSuggestionsResponse,
  EventReviewListResponse,
  EventReviewRecord,
  GuidanceResponse,
  NarrativeResponse,
  ColumnMappingResponse,
  AuditEvent,
  CaseSummary,
  EntityDetail,
  EntityRecord,
  EventListResponse,
  Evidence,
  Finding,
  FindingListResponse,
  GraphResponse,
  HashVerifyResponse,
  InvestigatorAnnotation,
  Health,
  ParseResponse,
  ReconstructionResponse,
  RelationshipDetail,
  RelationshipListResponse,
  ReportRecord,
  SpatialResponse,
  TimelineResponse,
} from "@/types";

export const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ?? "/api"
).replace(/\/+$/, "");

let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
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
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  if (options.caseId) headers["X-Case-ID"] = options.caseId;

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
    credentials: "include",
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
  loginGoogle: (credential: string) =>
    request<import("@/types").AuthSession>("/auth/google", {
      method: "POST",
      body: { credential },
    }),
  loginDemo: () => request<import("@/types").AuthSession>("/auth/demo", { method: "POST" }),
  me: () => request<import("@/types").AuthUser>("/auth/me"),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),


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
  getColumnMapping: (caseId: string, evidenceId: string) =>
    request<ColumnMappingResponse>(
      `/evidence/${evidenceId}/mapping${query({ case_id: caseId })}`,
      { caseId },
    ),
  saveColumnMapping: (
    caseId: string,
    evidenceId: string,
    mapping: Record<string, string | null>,
  ) =>
    request<ColumnMappingResponse>(
      `/evidence/${evidenceId}/mapping${query({ case_id: caseId })}`,
      { method: "PUT", caseId, body: { mapping } },
    ),
  getEvidenceContentUrl: (caseId: string, evidenceId: string) =>
    `${API_BASE}/evidence/${evidenceId}/content${query({ case_id: caseId })}`,

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
  timeline: (
    caseId: string,
    params: {
      limit?: number;
      start?: string;
      end?: string;
      evidence_id?: string;
      event_type?: string;
    } = {},
  ) =>
    request<TimelineResponse>(
      `/cases/${caseId}/timeline${query({ limit: params.limit ?? 1000, ...params })}`,
      { caseId },
    ),
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
  getEntityDetail: (caseId: string, entityId: string) =>
    request<EntityDetail>(`/cases/${caseId}/entities/${entityId}`, { caseId }),
  listRelationships: (
    caseId: string,
    params: {
      relationship_type?: string;
      classification?: string;
      review_status?: string;
      confidence?: string;
      limit?: number;
    } = {},
  ) =>
    request<RelationshipListResponse>(
      `/cases/${caseId}/relationships${query(params)}`,
      { caseId },
    ),
  getRelationship: (caseId: string, relationshipId: string) =>
    request<RelationshipDetail>(
      `/relationships/${relationshipId}${query({ case_id: caseId })}`,
      { caseId },
    ),
  reviewRelationship: (
    caseId: string,
    relationshipId: string,
    payload: { decision: string; reviewer?: string; note?: string },
  ) =>
    request<RelationshipDetail>(
      `/relationships/${relationshipId}/review${query({ case_id: caseId })}`,
      { method: "POST", caseId, body: payload },
    ),
  spatial: (caseId: string) =>
    request<SpatialResponse>(`/cases/${caseId}/spatial`, { caseId }),
  reconstruction: (caseId: string) =>
    request<ReconstructionResponse>(`/cases/${caseId}/reconstruction`, { caseId }),

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
    `${API_BASE}/cases/${caseId}/auth/export${query({ format })}`,

  aiStatus: () => request<AiStatus>("/ai/status"),
  askAi: (
    caseId: string,
    payload: { question: string; focus_type?: string | null; focus_id?: string | null },
  ) =>
    request<AiAnswer>(`/cases/${caseId}/ai/ask`, {
      method: "POST",
      caseId,
      body: payload,
    }),
  listAnnotations: (caseId: string) =>
    request<InvestigatorAnnotation[]>(`/cases/${caseId}/annotations`, { caseId }),
  createAnnotation: (
    caseId: string,
    payload: {
      target_type: string;
      target_id: string;
      author?: string;
      note: string;
    },
  ) =>
    request<InvestigatorAnnotation>(`/cases/${caseId}/annotations`, {
      method: "POST",
      caseId,
      body: payload,
    }),

  guidance: (caseId: string) =>
    request<GuidanceResponse>(`/cases/${caseId}/guidance`, { caseId }),
  narrative: (caseId: string) =>
    request<NarrativeResponse>(`/cases/${caseId}/narrative`, { caseId }),
  reviewEvent: (
    caseId: string,
    eventId: string,
    payload: { decision: "relevant" | "not_relevant" | "needs_review"; reviewer?: string; note?: string },
  ) =>
    request<EventReviewRecord>(`/cases/${caseId}/events/${eventId}/review`, {
      method: "POST",
      caseId,
      body: payload,
    }),
  listEventReviews: (caseId: string) =>
    request<EventReviewListResponse>(`/cases/${caseId}/event-reviews`, { caseId }),
  aiSuggestions: (caseId: string) =>
    request<AiSuggestionsResponse>(`/cases/${caseId}/ai/suggestions`, { caseId }),

  listReports: (caseId: string) => request<ReportRecord[]>(`/cases/${caseId}/reports`, { caseId }),
  generateReport: (caseId: string, reportType: "pdf" | "json") =>
    request<ReportRecord>(`/cases/${caseId}/reports`, {
      method: "POST",
      caseId,
      body: { report_type: reportType },
    }),
  getReportDownloadUrl: (caseId: string, reportId: string) =>
    `${API_BASE}/reports/${reportId}/download${query({ case_id: caseId })}`,
};
