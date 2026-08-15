import { expect, test } from "vitest";
import { normalizedBboxToImage, normalizedPointsToImage } from "./graph-geometry";

test("converts a normalized bounding box to native image coordinates", () => {
  expect(normalizedBboxToImage(
    { x: 0.1, y: 0.25, width: 0.3, height: 0.5 },
    { width: 2000, height: 1000 },
  )).toEqual({ x: 200, y: 250, width: 600, height: 500 });
});

test("converts a normalized polyline to native image coordinates", () => {
  expect(normalizedPointsToImage(
    [{ x: 0.1, y: 0.2 }, { x: 0.8, y: 0.9 }],
    { width: 1000, height: 500 },
  )).toEqual([100, 100, 800, 450]);
});
