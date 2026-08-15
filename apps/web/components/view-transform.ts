export type Point = { x: number; y: number };
export type ViewTransform = Point & { scale: number };

export const MIN_SCALE = 0.05;
export const MAX_SCALE = 16;

export function fitTransform(
  container: { width: number; height: number },
  image: { width: number; height: number },
  padding = 24,
): ViewTransform {
  if (container.width <= 0 || container.height <= 0 || image.width <= 0 || image.height <= 0) {
    return { x: 0, y: 0, scale: 1 };
  }
  const availableWidth = Math.max(1, container.width - padding * 2);
  const availableHeight = Math.max(1, container.height - padding * 2);
  const scale = clampScale(Math.min(availableWidth / image.width, availableHeight / image.height));
  return {
    x: (container.width - image.width * scale) / 2,
    y: (container.height - image.height * scale) / 2,
    scale,
  };
}

export function zoomAtPoint(
  view: ViewTransform,
  pointer: Point,
  requestedScale: number,
): ViewTransform {
  const scale = clampScale(requestedScale);
  const imagePoint = {
    x: (pointer.x - view.x) / view.scale,
    y: (pointer.y - view.y) / view.scale,
  };
  return {
    x: pointer.x - imagePoint.x * scale,
    y: pointer.y - imagePoint.y * scale,
    scale,
  };
}

export function clampScale(scale: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
}
