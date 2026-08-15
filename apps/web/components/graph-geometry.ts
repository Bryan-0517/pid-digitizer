import type { BoundingBox, Point } from "../types/engineering-graph";

export type ImageSize = { width: number; height: number };

export function normalizedBboxToImage(bbox: BoundingBox, image: ImageSize): BoundingBox {
  return {
    x: bbox.x * image.width,
    y: bbox.y * image.height,
    width: bbox.width * image.width,
    height: bbox.height * image.height,
  };
}

export function normalizedPointsToImage(points: Point[], image: ImageSize): number[] {
  return points.flatMap((point) => [point.x * image.width, point.y * image.height]);
}
