import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React, { useImperativeHandle, useState } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import DiagramViewer from "./diagram-viewer";
import type { EngineeringGraph } from "../types/engineering-graph";

vi.mock("react-konva", () => ({
  Stage: React.forwardRef(function MockStage(
    props: React.PropsWithChildren<Record<string, unknown>>,
    ref: React.ForwardedRef<unknown>,
  ) {
    const stage = {
      getPointerPosition: () => ({ x: 400, y: 300 }),
      stopDrag: vi.fn(),
      getStage: () => stage,
    };
    useImperativeHandle(ref, () => stage);
    const onWheel = props.onWheel as ((event: unknown) => void) | undefined;
    const onClick = props.onClick as ((event: unknown) => void) | undefined;
    return (
      <div
        data-testid="konva-stage"
        data-width={String(props.width)}
        data-height={String(props.height)}
        onWheel={(event) => onWheel?.({ evt: event.nativeEvent })}
        onClick={() => onClick?.({ target: stage })}
      >
        {props.children}
      </div>
    );
  }),
  Layer: ({ children, name }: React.PropsWithChildren<{ name?: string }>) => (
    <div data-testid={name ? `${name}-layer` : undefined}>{children}</div>
  ),
  Image: ({ width, height }: { width: number; height: number }) => (
    <div data-testid="konva-image" data-width={width} data-height={height} />
  ),
  Group: ({ children, id, onClick }: React.PropsWithChildren<{
    id: string;
    onClick?: (event: { cancelBubble: boolean }) => void;
  }>) => (
    <button
      type="button"
      data-testid={`entity-${id}`}
      onClick={(event) => {
        event.stopPropagation();
        onClick?.({ cancelBubble: false });
      }}
    >{children}</button>
  ),
  Rect: ({ stroke }: { stroke: string }) => <span data-testid="entity-rect" data-stroke={stroke} />,
  Text: ({ text }: { text: string }) => <span data-testid="entity-label">{text}</span>,
  Line: ({ id, onClick, stroke }: { id: string; stroke: string; onClick?: (event: { cancelBubble: boolean }) => void }) => <button type="button" data-testid="connection-line" data-connection-id={id} data-stroke={stroke} onClick={(event) => { event.stopPropagation(); onClick?.({ cancelBubble: false }); }} />,
}));

const graph = testGraph();

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
      graph={graph}
      selectedEntityId={null}
      selectedConnectionId={null}
      onSelectEntity={vi.fn()}
      onSelectConnection={vi.fn()}
      onClearSelection={vi.fn()}
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
      graph={graph}
      selectedEntityId={null}
      selectedConnectionId={null}
      onSelectEntity={vi.fn()}
      onSelectConnection={vi.fn()}
      onClearSelection={vi.fn()}
    />,
  );

  fireEvent.wheel(screen.getByTestId("konva-stage"), { deltaY: -1 });
  await waitFor(() => expect(screen.getByLabelText("Zoom level")).toHaveTextContent("51%"));
  fireEvent.click(screen.getByRole("button", { name: "Fit to screen" }));
  expect(screen.getByLabelText("Zoom level")).toHaveTextContent("47%");
});

test("renders entity labels with tag, display name, and id fallbacks", () => {
  renderViewer();

  expect(screen.getByText("P-MOCK-1")).toBeInTheDocument();
  expect(screen.getByText("Mock indicator")).toBeInTheDocument();
  expect(screen.getByText("mock-boundary-1")).toBeInTheDocument();
});

test("selects one entity and clears selection from the background", () => {
  renderViewer();

  fireEvent.click(screen.getByTestId("entity-mock-valve-1"));
  expect(screen.getByLabelText("Selected entity")).toHaveTextContent("mock-valve-1");
  expect(screen.getAllByTestId("entity-rect")[1]).toHaveAttribute("data-stroke", "#facc15");

  fireEvent.click(screen.getByTestId("konva-stage"));
  expect(screen.getByLabelText("Selected entity")).toHaveTextContent("None");
});

test("entity and connection layer controls toggle independently", () => {
  renderViewer();
  expect(screen.getByTestId("entities-layer")).toBeInTheDocument();
  expect(screen.getByTestId("connections-layer")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("checkbox", { name: "Entities" }));
  expect(screen.queryByTestId("entities-layer")).not.toBeInTheDocument();
  expect(screen.getByTestId("connections-layer")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("checkbox", { name: "Connections" }));
  expect(screen.queryByTestId("connections-layer")).not.toBeInTheDocument();
});

test("renders only a connection with explicit polyline geometry", () => {
  renderViewer();

  expect(screen.getAllByTestId("connection-line")).toHaveLength(1);
  expect(screen.getByTestId("connection-line")).toHaveAttribute(
    "data-connection-id",
    "mock-connection-with-geometry",
  );
});

test("selects a rendered connection independently", () => {
  renderViewer();
  fireEvent.click(screen.getByTestId("connection-line"));
  expect(screen.getByLabelText("Selected connection")).toHaveTextContent("mock-connection-with-geometry");
  expect(screen.getByLabelText("Selected entity")).toHaveTextContent("None");
});

function renderViewer() {
  return render(<ViewerHarness />);
}

function ViewerHarness() {
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedConnection, setSelectedConnection] = useState<string | null>(null);
  return (
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
      graph={graph}
      selectedEntityId={selected}
      selectedConnectionId={selectedConnection}
      onSelectEntity={(id) => { setSelected(id); if (id) setSelectedConnection(null); }}
      onSelectConnection={(id) => { setSelectedConnection(id); if (id) setSelected(null); }}
      onClearSelection={() => { setSelected(null); setSelectedConnection(null); }}
    />
  );
}

function testGraph(): EngineeringGraph {
  const base = {
    documentId: "doc-1", pageId: "page-1", properties: {},
    assertion: { mode: "human_added" as const, reviewStatus: "unreviewed" as const },
    provenance: [], createdAt: "2026-01-01T00:00:00Z", updatedAt: "2026-01-01T00:00:00Z",
  };
  return {
    schemaVersion: "0.1", documentId: "doc-1", metadata: {},
    entities: [
      { ...base, id: "mock-equipment-1", kind: "equipment", tag: "P-MOCK-1", geometry: { bbox: { x: .1, y: .1, width: .1, height: .1 } } },
      { ...base, id: "mock-valve-1", kind: "valve", tag: "V-MOCK-1", geometry: { bbox: { x: .3, y: .1, width: .1, height: .1 } } },
      { ...base, id: "mock-instrument-1", kind: "instrument", displayName: "Mock indicator", geometry: { bbox: { x: .5, y: .1, width: .1, height: .1 } } },
      { ...base, id: "mock-boundary-1", kind: "boundary", geometry: { bbox: { x: .7, y: .1, width: .1, height: .1 } } },
    ],
    connections: [
      { ...base, id: "mock-connection-with-geometry", sourceEntityId: "mock-equipment-1", targetEntityId: "mock-valve-1", kind: "process", geometry: { polyline: [{ x: .2, y: .2 }, { x: .3, y: .2 }] } },
      { ...base, id: "mock-connection-without-geometry", sourceEntityId: "mock-valve-1", targetEntityId: "mock-boundary-1", kind: "process" },
    ],
  };
}
