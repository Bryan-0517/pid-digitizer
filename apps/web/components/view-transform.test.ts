import { expect, test } from "vitest";
import { fitTransform, zoomAtPoint } from "./view-transform";

test("fits and centers an image while preserving its aspect ratio", () => {
  expect(fitTransform({ width: 1000, height: 700 }, { width: 1600, height: 800 }, 20))
    .toEqual({ x: 20, y: 110, scale: 0.6 });
});

test("keeps the image point under the pointer fixed while zooming", () => {
  const pointer = { x: 300, y: 200 };
  const before = { x: 100, y: 50, scale: 0.5 };
  const after = zoomAtPoint(before, pointer, 1);

  expect(after).toEqual({ x: -100, y: -100, scale: 1 });
  expect((pointer.x - after.x) / after.scale).toBe((pointer.x - before.x) / before.scale);
  expect((pointer.y - after.y) / after.scale).toBe((pointer.y - before.y) / before.scale);
});
