import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClassificationBadge } from "./ClassificationBadge";

describe("ClassificationBadge", () => {
  it.each([
    ["observation", "Observation"],
    ["correlation", "Correlation"],
    ["inference", "Inference"],
    ["hypothesis", "Hypothesis"],
  ])("renders %s classification", (value, label) => {
    render(<ClassificationBadge classification={value} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
