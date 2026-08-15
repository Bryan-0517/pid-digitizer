import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React, { useImperativeHandle } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import DiagramViewer from "./diagram-viewer";

vi.mock("react-konva", () => ({
  Stage: React.forwardRef(function MockStage(
    props: React.PropsWithChildren<Record<string, unknown>>,
    ref: React.ForwardedRef<unknown>,
  ) {
    useImperativeHandle(ref, () => ({
      getPointerPosition: () => ({ x: 400, y: 300 }),
      stopDrag: vi.fn(),
    }));
    const onWheel = props.onWheel as ((event: unknown) => void) | undefined;
    return (
      <div
        data-testid="konva-stage"
        data-width={String(props.width)}
        data-height={String(props.height)}
        onWheel={(event) => onWheel?.({ evt: event.nativeEvent })}
      >
        {props.children}
      </div>
    );
  }),
  Layer: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  Image: ({ width, height }: { width: number; height: number }) => (
    <div data-testid="konva-image" data-width={width} data-height={height} />
  ),
}));

class ResizeObserverMock {
  constructor(private callback: ResizeObserverCallback) {}
  observe() {
    this.callback(
      [{ contentRect: { width: 800, height: 600 } } as ResizeObserverEntry],
      this as unknown as ResizeObserver,
    );
  }
  disconnect() {}
  unobserve() {}
}

class ImageMock {
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private source = "";
  set src(value: string) {
    this.source = value;
    queueMicrotask(() => this.onload?.());
  }
  get src() { return this.source; }
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", ResizeObserverMock);
  vi.stubGlobal("Image", ImageMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("mounts the page image at native dimensions inside a responsive stage", async () => {
  render(
    <DiagramViewer
      documentName="diagram.png"
      imageUrl="http://localhost:8000/files/page.png"
      page={{
        id: "page-1",
        documentId: "doc-1",
        pageNumber: 1,
        imageUri: "/files/page.png",
        widthPx: 1600,
        heightPx: 800,
      }}
    />,
  );

  expect(screen.getByTestId("konva-stage")).toHaveAttribute("data-width", "800");
  await waitFor(() => expect(screen.getByTestId("konva-image")).toHaveAttribute("data-width", "1600"));
  expect(screen.getByTestId("konva-image")).toHaveAttribute("data-height", "800");
  expect(screen.getByLabelText("Zoom level")).toHaveTextContent("47%");
});

test("fit-to-screen restores the fitted transform after pointer zoom", async () => {
  render(
    <DiagramViewer
      documentName="diagram.png"
      imageUrl="http://localhost:8000/files/page.png"
      page={{
        id: "page-1",
        documentId: "doc-1",
        pageNumber: 1,
        imageUri: "/files/page.png",
        widthPx: 1600,
        heightPx: 800,
      }}
    />,
  );

  fireEvent.wheel(screen.getByTestId("konva-stage"), { deltaY: -1 });
  await waitFor(() => expect(screen.getByLabelText("Zoom level")).toHaveTextContent("51%"));
  fireEvent.click(screen.getByRole("button", { name: "Fit to screen" }));
  expect(screen.getByLabelText("Zoom level")).toHaveTextContent("47%");
});
