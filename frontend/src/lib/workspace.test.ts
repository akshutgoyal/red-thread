import { describe, expect, it } from "vitest";
import { hasActiveCase } from "./caseNavigation";

describe("empty workspace permissions", () => {
  it("keeps investigation actions disabled until a case is selected", () => {
    expect(hasActiveCase(null)).toBe(false);
    expect(hasActiveCase("")).toBe(false);
  });

  it("enables investigation actions once a case exists", () => {
    expect(hasActiveCase("case-123")).toBe(true);
  });
});
