export type CaseStatus = "open" | "in_review" | "closed";
export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type FindingStatus =
  | "open"
  | "needs_review"
  | "accepted"
  | "rejected"
  | "needs_more_evidence";

export interface CaseSummary {
  id: string;
  title: string;
  description: string;
  status: CaseStatus;
  investigator_notes: string;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
  evidence_count: number;
  event_count: number;
  finding_count: number;
  open_finding_count: number;
}

export interface Evidence {
  id: string;
  case_id: string;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  uploaded_at: string;
  parser_name: string | null;
  parser_version: string | null;
  processing_status: string;
  processing_error: string | null;
  metadata_json: Record<string, unknown>;
  hash_verified: boolean;
  hash_verified_at: string | null;
}

export interface HashVerifyResponse {
  evidence_id: string;
  expected_sha256: string;
  actual_sha256: string;
  verified: boolean;
  checked_at: string;
  message: string;
}

export interface ParseResponse {
  evidence_id: string;
  parser_name: string;
  parser_version: string;
  events_created: number;
  findings_created: number;
  warnings: string[];
  summary: Record<string, unknown>;
  status: string;
}

export interface EventRecord {
  id: string;
  case_id: string;
  evidence_id: string;
  event_type: string;
  timestamp_raw: string | null;
  timestamp_normalized: string | null;
  timestamp_confidence: string;
  timestamp_timezone: string | null;
  source_filename: string;
  source_locator: string;
  source_snippet: string;
  attributes_json: Record<string, unknown>;
  warnings_json: string[];
  parser_name: string;
  parser_version: string;
  created_at: string;
}

export interface EventListResponse {
  items: EventRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface TimelineResponse {
  items: EventRecord[];
  undated: EventRecord[];
  total: number;
}

export interface EntityRecord {
  id: string;
  case_id: string;
  entity_type: string;
  value_original: string;
  value_normalized: string;
  normalization_method: string;
  event_count?: number;
  evidence_ids?: string[];
  first_seen_at?: string | null;
  last_seen_at?: string | null;
}

export interface GraphNode {
  id: string;
  label: string;
  node_type: string;
  data: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  edge_type: string;
  match_method: string;
  explanation: string;
  confidence: string;
  supporting_event_ids: string[];
  supporting_evidence_ids: string[];
  relationship_id?: string | null;
  relationship_type?: string | null;
  correlation_rule?: string | null;
  classification?: string | null;
  review_status?: string | null;
  data?: Record<string, unknown>;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface FindingEvidence {
  evidence_id: string;
  event_id: string | null;
  role: string;
  source_locator: string;
}

export interface Finding {
  id: string;
  case_id: string;
  severity: Severity;
  category: string;
  title: string;
  explanation: string;
  detection_method: string;
  confidence: string;
  status: FindingStatus;
  limitations: string;
  alternative_explanations: string;
  reviewer_note: string;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
  evidence_links: FindingEvidence[];
}

export interface FindingListResponse {
  items: Finding[];
  total: number;
}

export interface AuditEvent {
  id: string;
  case_id: string;
  evidence_id: string | null;
  actor: string;
  action: string;
  details_json: Record<string, unknown>;
  created_at: string;
}

export interface Health {
  status: string;
  app: string;
  version: string;
  database: string;
  ai_provider: string;
  ai_configured: boolean;
  ocr_available: boolean;
}

export interface AiStatus {
  configured: boolean;
  provider: "commandcode" | "tokenharbor" | "none" | string;
  model: string;
  model_label: string;
  base_url_host: string;
  reason: string;
}

export interface AiCitation {
  kind: string;
  id: string;
  label: string;
  evidence_id?: string | null;
  event_id?: string | null;
  source_locator?: string | null;
  verified: boolean;
  warning?: string;
}

export interface AiAnswer {
  answer: string;
  citations: AiCitation[];
  uncertainties: string[];
  alternative_explanations: string[];
  suggested_next_steps: string[];
  insufficient_evidence: boolean;
  provider: string;
  model: string;
  model_label: string;
  ai_generated: boolean;
  usage?: Record<string, unknown>;
}

export interface ReportRecord {
  id: string;
  case_id: string;
  report_type: string;
  filename: string;
  status: string;
  metadata?: Record<string, unknown>;
  generated_at: string;
}

export interface RelationshipSupport {
  id: string;
  relationship_id: string;
  evidence_id: string | null;
  event_id: string | null;
  finding_id: string | null;
  source_locator: string;
  snippet: string;
  support_kind: string;
  created_at: string;
}

export interface ReviewDecision {
  id: string;
  case_id: string;
  target_type: string;
  target_id: string;
  decision: string;
  reviewer: string;
  note: string;
  created_at: string;
}

export interface Relationship {
  id: string;
  case_id: string;
  source_type: string;
  source_id: string;
  target_type: string;
  target_id: string;
  relationship_type: string;
  correlation_rule: string;
  explanation: string;
  confidence: string;
  classification: string;
  review_status: string;
  review_note: string;
  metadata_json: Record<string, unknown>;
  support_count: number;
  created_at: string;
  updated_at: string;
}

export interface RelationshipDetail extends Relationship {
  supports: RelationshipSupport[];
  reviews: ReviewDecision[];
}

export interface RelationshipListResponse {
  items: Relationship[];
  total: number;
}

export interface InvestigatorAnnotation {
  id: string;
  case_id: string;
  target_type: string;
  target_id: string;
  author: string;
  note: string;
  created_at: string;
}


export interface EntityDetail {
  entity: EntityRecord;
  events: EventRecord[];
  relationships: Relationship[];
  evidence_ids: string[];
  mention_count: number;
}

export interface SpatialObservation {
  event_id: string;
  evidence_id: string;
  event_type: string;
  source_filename: string;
  source_locator: string;
  timestamp_normalized: string | null;
  latitude: number;
  longitude: number;
  label: string;
  entity_ids: string[];
  entity_values: string[];
}

export interface SpatialResponse {
  observations: SpatialObservation[];
  relationships: Relationship[];
  total: number;
}

export interface ReconstructionResponse {
  case_id: string;
  counts: Record<string, number>;
  relationship_types: Record<string, number>;
  review_statuses: Record<string, number>;
  relationships: Relationship[];
  recent_events: EventRecord[];
  conflicts: Finding[];
  unresolved: string[];
  spatial_observations: SpatialObservation[];
  generated_at: string;
  limitations: string[];
}


export interface AuthUser {
  id: string;
  email: string;
  name: string;
  picture: string | null;
  is_demo: boolean;
}

export interface AuthSession {
  token: string;
  user: AuthUser;
}
