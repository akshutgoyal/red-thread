import { describe, expect, it } from "vitest";
import { casePathForSelection, hasActiveCase } from "./caseNavigation";

describe("case navigation", () => {
  it("keeps the current investigation subpage when the case changes", () => {
    expect(casePathForSelection("/cases/old/timeline", "new")).toBe("/cases/new/timeline");
    expect(casePathForSelection("/cases/old/graph", "new")).toBe("/cases/new/graph");
    expect(casePathForSelection("/cases/old", "new")).toBe("/cases/new");
  });

  it("does not rewrite non-case routes", () => {
    expect(casePathForSelection("/", "new")).toBeNull();
    expect(casePathForSelection("/cases", "new")).toBeNull();
    expect(casePathForSelection("/login", "new")).toBeNull();
  });

  it("recognizes an active case id", () => {
    expect(hasActiveCase("case-123")).toBe(true);
    expect(hasActiveCase("  case-123  ")).toBe(true);
    expect(hasActiveCase("")).toBe(false);
    expect(hasActiveCase(null)).toBe(false);
    expect(hasActiveCase(undefined)).toBe(false);
  });
});
