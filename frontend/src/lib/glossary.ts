/**
 * One-line explanations for technical terms.
 *
 * Each definition is a single plain-English sentence. Components reference a
 * term by key so the same wording appears everywhere it is explained.
 */
export const GLOSSARY: Record<string, string> = {
  sha256:
    "A unique digital fingerprint used to check whether a file has changed.",
  provenance:
    "Information showing where evidence came from and how it was handled.",
  entity:
    "A person, phone number, account or other identifiable item found in evidence.",
  normalized_event:
    "Information from different sources converted into a common format.",
  correlation:
    "Finding connections between information from different evidence sources.",
  temporal_lead:
    "A possible connection suggested by events occurring around the same time.",
  confidence:
    "An indication of how strongly the available information supports a connection.",
  metadata:
    "Additional information stored alongside a file, such as its date or device details.",
  integrity:
    "Confirmation that evidence has not changed since its recorded hash was generated.",
  raw_edge:
    "An original connection record before it is combined or interpreted.",
  review_status:
    "The current stage of an investigator's review of an item.",
  relationship:
    "A connection between two entities that is backed by at least one stored record.",
  documented_relationship:
    "A connection supported directly by source evidence rather than inferred.",
  inferred_lead:
    "A possible connection that still needs supporting evidence before it can be trusted.",
  unique_connection:
    "One entity pair, counted once even when several rules describe the same pair.",
  finding: "An observation about the case that an investigator must review.",
  hypothesis:
    "A proposed explanation that is not yet supported by verified evidence.",
  entity_match:
    "Two records that contain the same identifier, such as one phone number.",
  timeline:
    "The order in which recorded events happened, across every evidence source.",
  spatial:
    "Where recorded events happened, based only on location data in the evidence.",
};

/** Human label paired with its explanation, for showing inline help. */
export interface GlossaryEntry {
  label: string;
  explanation: string;
}

export function glossary(key: keyof typeof GLOSSARY): GlossaryEntry {
  return { label: key, explanation: GLOSSARY[key] ?? "" };
}
