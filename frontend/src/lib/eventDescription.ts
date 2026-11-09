import { humanize } from "@/lib/format";
import type { EventRecord } from "@/types";

const KEY_LABELS: Record<string, string> = {
  from_number: "from",
  to_number: "to",
  source_number: "from",
  destination_number: "to",
  caller: "caller",
  callee: "callee",
  sender: "from",
  recipient: "to",
  phone_number: "phone",
  device_id: "device",
  username: "account",
  source_ip: "IP",
  ip_address: "IP",
  auth_status: "result",
  amount: "amount",
  currency: "currency",
  utr: "UTR",
  payee_vpa: "payee",
  payer_vpa: "payer",
  latitude: "lat",
  longitude: "lon",
  location: "location",
  camera_id: "camera",
  duration_seconds: "duration",
  message: "message",
  text: "text",
  body: "text",
};

/** Fields that make an event readable at a glance, in priority order. */
const SUMMARY_KEYS = [
  "message",
  "text",
  "body",
  "from_number",
  "source_number",
  "sender",
  "caller",
  "to_number",
  "destination_number",
  "recipient",
  "callee",
  "phone_number",
  "username",
  "auth_status",
  "source_ip",
  "ip_address",
  "device_id",
  "amount",
  "payee_vpa",
  "utr",
  "camera_id",
  "location",
];

/**
 * Build a short human description from stored attributes.
 *
 * Nothing is invented: every fragment comes from a field the parser recorded,
 * and the raw record stays available in the event drawer.
 */
export function describeEvent(event: EventRecord): string {
  const attributes = event.attributes_json ?? {};
  const parts: string[] = [];
  for (const key of SUMMARY_KEYS) {
    const value = attributes[key];
    if (value === undefined || value === null || value === "") continue;
    const label = KEY_LABELS[key] ?? humanize(key).toLowerCase();
    const rendered = typeof value === "string" ? value : String(value);
    if (rendered.length > 80) continue;
    parts.push(`${label} ${rendered}`);
    if (parts.length >= 3) break;
  }
  if (parts.length > 0) return `${humanize(event.event_type)} — ${parts.join(", ")}`;
  const snippet = event.source_snippet?.trim();
  if (snippet) {
    return snippet.length > 120 ? `${snippet.slice(0, 120)}…` : snippet;
  }
  return humanize(event.event_type);
}

/** Category used by the timeline filter chips. */
export function eventCategory(eventType: string): string {
  const value = eventType.toLowerCase();
  if (value.includes("call")) return "call";
  if (value.includes("message") || value.includes("chat") || value.includes("sms")) {
    return "message";
  }
  if (value.includes("auth") || value.includes("login") || value.includes("sign")) {
    return "authentication";
  }
  if (value.includes("device") || value.includes("cctv") || value.includes("gps")) {
    return "device";
  }
  if (value.includes("transaction") || value.includes("payment") || value.includes("invoice")) {
    return "transaction";
  }
  if (value.includes("email") || value.includes("mail")) return "email";
  return "other";
}

export const EVENT_CATEGORIES = [
  { value: "call", label: "Calls" },
  { value: "message", label: "Messages" },
  { value: "authentication", label: "Authentication" },
  { value: "device", label: "Device activity" },
  { value: "transaction", label: "Transactions" },
  { value: "email", label: "Email" },
] as const;
