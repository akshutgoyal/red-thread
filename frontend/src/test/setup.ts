import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Vitest does not enable Testing Library's automatic cleanup unless `globals`
// is on, so unmount rendered trees between tests explicitly. Without this,
// queries find elements from earlier tests in the same file.
afterEach(() => {
  cleanup();
});
