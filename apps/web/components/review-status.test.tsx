import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, expect, test } from "vitest";
import ReviewStatus from "./review-status";

afterEach(cleanup);

test.each([
  ["confirmed", "observed"], ["corrected", "human_added"], ["unreviewed", "inferred"],
  ["needs_source", "observed"], ["rejected", "human_added"],
] as const)("renders exact canonical review %s and assertion %s", (reviewStatus, mode) => {
  render(<ReviewStatus confidence={0.731} assertion={{ reviewStatus, mode }} />);
  expect(screen.getByText("0.731")).toBeInTheDocument();
  expect(screen.getByText(reviewStatus)).toHaveClass(`review-${reviewStatus}`);
  expect(screen.getByText(mode)).toHaveClass(`assertion-${mode}`);
  expect(screen.queryByText(/high|medium|low/i)).not.toBeInTheDocument();
});

test("renders absent confidence without inventing a classification", () => {
  render(<ReviewStatus assertion={{ reviewStatus: "unreviewed", mode: "inferred" }} />);
  expect(screen.getByText("Not provided")).toBeInTheDocument();
});
