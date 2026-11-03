import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { FindingStatus } from "@/types";

export const queryKeys = {
  health: ["health"] as const,
  cases: ["cases"] as const,
  case: (caseId: string) => ["case", caseId] as const,
  evidence: (caseId: string) => ["evidence", caseId] as const,
  events: (caseId: string, filters?: Record<string, unknown>) =>
    ["events", caseId, filters ?? {}] as const,
  timeline: (caseId: string) => ["timeline", caseId] as const,
  graph: (caseId: string, includeTemporal: boolean) =>
    ["graph", caseId, includeTemporal] as const,
  entities: (caseId: string) => ["entities", caseId] as const,
  entity: (caseId: string, entityId: string) => ["entity", caseId, entityId] as const,
  relationships: (caseId: string, filters?: Record<string, unknown>) =>
    ["relationships", caseId, filters ?? {}] as const,
  relationship: (caseId: string, relationshipId: string) =>
    ["relationship", caseId, relationshipId] as const,
  spatial: (caseId: string) => ["spatial", caseId] as const,
  reconstruction: (caseId: string) => ["reconstruction", caseId] as const,
  findings: (caseId: string, filters?: Record<string, unknown>) =>
    ["findings", caseId, filters ?? {}] as const,
  audit: (caseId: string) => ["audit", caseId] as const,
  aiStatus: ["ai-status"] as const,
  reports: (caseId: string) => ["reports", caseId] as const,
};

export function useHealth() {
  return useQuery({ queryKey: queryKeys.health, queryFn: api.health, retry: 1 });
}

export function useCases() {
  return useQuery({ queryKey: queryKeys.cases, queryFn: api.listCases });
}

export function useCase(caseId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.case(caseId ?? ""),
    queryFn: () => api.getCase(caseId as string),
    enabled: Boolean(caseId),
  });
}

export function useEvidence(caseId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.evidence(caseId ?? ""),
    queryFn: () => api.listEvidence(caseId as string),
    enabled: Boolean(caseId),
  });
}

export function useEvents(
  caseId: string | undefined,
  filters: Parameters<typeof api.listEvents>[1] = {},
) {
  return useQuery({
    queryKey: queryKeys.events(caseId ?? "", filters),
    queryFn: () => api.listEvents(caseId as string, filters),
    enabled: Boolean(caseId),
  });
}

export function useTimeline(caseId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.timeline(caseId ?? ""),
    queryFn: () => api.timeline(caseId as string),
    enabled: Boolean(caseId),
  });
}

export function useGraph(caseId: string | undefined, includeTemporal: boolean) {
  return useQuery({
    queryKey: queryKeys.graph(caseId ?? "", includeTemporal),
    queryFn: () => api.graph(caseId as string, includeTemporal),
    enabled: Boolean(caseId),
  });
}

export function useEntities(caseId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.entities(caseId ?? ""),
    queryFn: () => api.listEntities(caseId as string),
    enabled: Boolean(caseId),
  });
}

export function useEntityDetail(caseId: string | undefined, entityId: string | null) {
  return useQuery({
    queryKey: queryKeys.entity(caseId ?? "", entityId ?? ""),
    queryFn: () => api.getEntityDetail(caseId as string, entityId as string),
    enabled: Boolean(caseId && entityId),
  });
}

export function useRelationships(
  caseId: string | undefined,
  filters: Parameters<typeof api.listRelationships>[1] = {},
) {
  return useQuery({
    queryKey: queryKeys.relationships(caseId ?? "", filters),
    queryFn: () => api.listRelationships(caseId as string, filters),
    enabled: Boolean(caseId),
  });
}

export function useRelationship(caseId: string | undefined, relationshipId: string | null) {
  return useQuery({
    queryKey: queryKeys.relationship(caseId ?? "", relationshipId ?? ""),
    queryFn: () => api.getRelationship(caseId as string, relationshipId as string),
    enabled: Boolean(caseId && relationshipId),
  });
}

export function useSpatial(caseId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.spatial(caseId ?? ""),
    queryFn: () => api.spatial(caseId as string),
    enabled: Boolean(caseId),
  });
}

export function useReconstruction(caseId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.reconstruction(caseId ?? ""),
    queryFn: () => api.reconstruction(caseId as string),
    enabled: Boolean(caseId),
  });
}

export function useFindings(
  caseId: string | undefined,
  filters: Parameters<typeof api.listFindings>[1] = {},
) {
  return useQuery({
    queryKey: queryKeys.findings(caseId ?? "", filters),
    queryFn: () => api.listFindings(caseId as string, filters),
    enabled: Boolean(caseId),
  });
}

export function useAudit(caseId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.audit(caseId ?? ""),
    queryFn: () => api.audit(caseId as string),
    enabled: Boolean(caseId),
  });
}

export function useAiStatus() {
  return useQuery({ queryKey: queryKeys.aiStatus, queryFn: api.aiStatus, retry: 1 });
}

export function useReports(caseId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.reports(caseId ?? ""),
    queryFn: () => api.listReports(caseId as string),
    enabled: Boolean(caseId),
    retry: false,
  });
}

function useCaseInvalidation(caseId: string) {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: queryKeys.case(caseId) });
    client.invalidateQueries({ queryKey: queryKeys.cases });
    client.invalidateQueries({ queryKey: ["evidence", caseId] });
    client.invalidateQueries({ queryKey: ["events", caseId] });
    client.invalidateQueries({ queryKey: queryKeys.timeline(caseId) });
    client.invalidateQueries({ queryKey: ["graph", caseId] });
    client.invalidateQueries({ queryKey: ["findings", caseId] });
    client.invalidateQueries({ queryKey: queryKeys.audit(caseId) });
    client.invalidateQueries({ queryKey: ["relationships", caseId] });
    client.invalidateQueries({ queryKey: ["relationship", caseId] });
    client.invalidateQueries({ queryKey: ["entity", caseId] });
    client.invalidateQueries({ queryKey: queryKeys.spatial(caseId) });
    client.invalidateQueries({ queryKey: queryKeys.reconstruction(caseId) });
  };
}

export function useCreateCase() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.createCase,
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.cases }),
  });
}

export function useUpdateCase(caseId: string) {
  const invalidate = useCaseInvalidation(caseId);
  return useMutation({
    mutationFn: (payload: Parameters<typeof api.updateCase>[1]) =>
      api.updateCase(caseId, payload),
    onSuccess: invalidate,
  });
}

export function useUploadEvidence(caseId: string) {
  const invalidate = useCaseInvalidation(caseId);
  return useMutation({
    mutationFn: (file: File) => api.uploadEvidence(caseId, file),
    onSuccess: invalidate,
  });
}

export function useVerifyEvidence(caseId: string) {
  const invalidate = useCaseInvalidation(caseId);
  return useMutation({
    mutationFn: (evidenceId: string) => api.verifyEvidence(caseId, evidenceId),
    onSuccess: invalidate,
  });
}

export function useParseEvidence(caseId: string) {
  const invalidate = useCaseInvalidation(caseId);
  return useMutation({
    mutationFn: ({
      evidenceId,
      reparse = false,
      parser,
    }: {
      evidenceId: string;
      reparse?: boolean;
      parser?: string;
    }) => api.parseEvidence(caseId, evidenceId, reparse, parser),
    onSuccess: invalidate,
  });
}

export function useReconcile(caseId: string) {
  const invalidate = useCaseInvalidation(caseId);
  return useMutation({
    mutationFn: () => api.reconcile(caseId),
    onSuccess: invalidate,
  });
}

export function useReviewFinding(caseId: string) {
  const invalidate = useCaseInvalidation(caseId);
  return useMutation({
    mutationFn: ({
      findingId,
      payload,
    }: {
      findingId: string;
      payload: { status: FindingStatus; reviewer_note?: string };
    }) => api.reviewFinding(caseId, findingId, payload),
    onSuccess: invalidate,
  });
}

export function useReviewRelationship(caseId: string) {
  const invalidate = useCaseInvalidation(caseId);
  return useMutation({
    mutationFn: ({
      relationshipId,
      payload,
    }: {
      relationshipId: string;
      payload: { decision: string; reviewer?: string; note?: string };
    }) => api.reviewRelationship(caseId, relationshipId, payload),
    onSuccess: invalidate,
  });
}

export function useAskAi(caseId: string) {
  return useMutation({
    mutationFn: (payload: Parameters<typeof api.askAi>[1]) =>
      api.askAi(caseId, payload),
  });
}

export function useCreateAnnotation(caseId: string) {
  return useMutation({
    mutationFn: (payload: Parameters<typeof api.createAnnotation>[1]) =>
      api.createAnnotation(caseId, payload),
  });
}

export function useGenerateReport(caseId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (reportType: "pdf" | "json") => api.generateReport(caseId, reportType),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.reports(caseId) }),
  });
}
