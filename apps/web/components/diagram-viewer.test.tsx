import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React, { useImperativeHandle, useState } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import DiagramViewer from "./diagram-viewer";
import type { EngineeringGraph } from "../types/engineering-graph";
import type { ProposalOverlayCandidate } from "../types/proposal-overlay";

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
  Rect: ({ name, stroke, strokeWidth, shadowColor, dash, opacity }: {
    name?: string; stroke: string; strokeWidth?: number; shadowColor?: string;
    dash?: number[]; opacity?: number;
  }) => <span
    data-testid={name === "entity-highlight-halo" ? "entity-highlight-halo"
      : name === "proposal-rect" ? "proposal-rect" : "entity-rect"}
    data-stroke={stroke}
    data-stroke-width={strokeWidth}
    data-shadow-color={shadowColor}
    data-dash={dash?.join(",")}
    data-opacity={opacity}
  />,
  Text: ({ text }: { text: string }) => <span data-testid="entity-label">{text}</span>,
  Line: ({ id, onClick, stroke }: { id: string; stroke: string; onClick?: (event: { cancelBubble: boolean }) => void }) => <button type="button" data-testid="connection-line" data-connection-id={id} data-stroke={stroke} onClick={(event) => { event.stopPropagation(); onClick?.({ cancelBubble: false }); }} />,
}));

const graph = testGraph();
const proposalCandidates: ProposalOverlayCandidate[] = [
  { candidateId: "proposal-equipment", kind: "equipment", tag: "V310001B",
    geometry: { bbox: { x: .05, y: .45, width: .07, height: .05 } } },
  { candidateId: "proposal-instrument", kind: "instrument", tag: "TE_0807A",
    geometry: { bbox: { x: .2, y: .65, width: .03, height: .03 } } },
];

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

test("renders entity labels without exposing internal ID fallbacks", () => {
  renderViewer();

  expect(screen.getByText("P-MOCK-1")).toBeInTheDocument();
  expect(screen.getByText("Mock indicator")).toBeInTheDocument();
  expect(screen.getByText("Unnamed boundary")).toBeInTheDocument();
  expect(screen.queryByText("mock-boundary-1")).not.toBeInTheDocument();
});

test("selects one entity and clears selection from the background", () => {
  renderViewer();

  fireEvent.click(screen.getByTestId("entity-mock-valve-1"));
  expect(screen.getAllByTestId("entity-rect")[1]).toHaveAttribute("data-stroke", "#facc15");

  fireEvent.click(screen.getByTestId("konva-stage"));
  expect(screen.getAllByTestId("entity-rect")[1]).toHaveAttribute("data-stroke", "#0ea5e9");
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

test("renders non-interactive proposal candidates separately and toggles their layer", () => {
  const onSelectEntity = vi.fn();
  render(
    <DiagramViewer
      documentName="IMG_6807.JPG" imageUrl="http://localhost/image.jpg"
      page={{ id: "page-1", documentId: "t019-demo-img6807", pageNumber: 1,
        imageUri: "/image.jpg", widthPx: 5000, heightPx: 3750 }}
      graph={graph} proposalCandidates={proposalCandidates}
      selectedEntityId={null} selectedConnectionId={null}
      onSelectEntity={onSelectEntity} onSelectConnection={vi.fn()} onClearSelection={vi.fn()}
    />,
  );

  expect(screen.getByTestId("proposals-layer")).toBeInTheDocument();
  expect(screen.getAllByTestId("proposal-rect")).toHaveLength(2);
  expect(screen.getAllByTestId("proposal-rect")[0]).toHaveAttribute("data-stroke", "#f97316");
  expect(screen.getAllByTestId("proposal-rect")[0]).toHaveAttribute("data-dash");
  expect(screen.getByLabelText("Zoom level")).toHaveTextContent("15%");
  expect(Number(screen.getAllByTestId("proposal-rect")[0].getAttribute("data-stroke-width")) * .1472)
    .toBeCloseTo(2.25);
  expect(screen.queryByText("V310001B · proposal")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Overlay legend")).toHaveTextContent("AI proposal — dashed");
  expect(onSelectEntity).not.toHaveBeenCalled();

  fireEvent.click(screen.getByTestId("entity-mock-equipment-1"));
  expect(onSelectEntity).toHaveBeenCalledWith("mock-equipment-1");
  fireEvent.click(screen.getByRole("checkbox", { name: "AI proposals" }));
  expect(screen.queryByTestId("proposals-layer")).not.toBeInTheDocument();
  expect(screen.getByTestId("entities-layer")).toBeInTheDocument();
});

test("renders only a connection with explicit polyline geometry", () => {
  renderViewer();

  expect(screen.getAllByTestId("connection-line")).toHaveLength(1);
  expect(screen.getByTestId("connection-line")).toHaveAttribute(
    "data-connection-id",
    "mock-connection-with-geometry",
  );
});

test("does not fabricate a path for a geometry-less connection", () => {
  renderViewer();

  expect(screen.getAllByTestId("connection-line")).toHaveLength(1);
  expect(screen.queryByTestId("connection-line-without-geometry")).not.toBeInTheDocument();
});

test("selects a rendered connection independently", () => {
  renderViewer();
  fireEvent.click(screen.getByTestId("connection-line"));
  expect(screen.getByTestId("connection-line")).toHaveAttribute("data-stroke", "#facc15");
});

test("renders stronger entity highlights and non-geometric topology independently from selection", () => {
  render(
    <DiagramViewer
      documentName="diagram.png"
      imageUrl="http://localhost:8000/files/page.png"
      page={{ id: "page-1", documentId: "doc-1", pageNumber: 1,
        imageUri: "/files/page.png", widthPx: 1600, heightPx: 800 }}
      graph={graph}
      selectedEntityId="mock-equipment-1"
      selectedConnectionId={null}
      highlightedEntityIds={["mock-equipment-1", "mock-valve-1", "mock-instrument-1"]}
      highlightedConnectionIds={["mock-connection-with-geometry", "mock-connection-without-geometry"]}
      onSelectEntity={vi.fn()}
      onSelectConnection={vi.fn()}
      onClearSelection={vi.fn()}
    />,
  );

  const entityStrokes = screen.getAllByTestId("entity-rect")
    .map((item) => item.getAttribute("data-stroke"));
  expect(entityStrokes).toEqual(["#facc15", "#c084fc", "#c084fc", "#0ea5e9"]);
  const halos = screen.getAllByTestId("entity-highlight-halo");
  expect(halos).toHaveLength(3);
  expect(halos.every((item) => item.getAttribute("data-stroke") === "#f5d0fe")).toBe(true);
  expect(halos.every((item) => item.getAttribute("data-shadow-color") === "#d946ef")).toBe(true);
  expect(screen.getAllByTestId("connection-line")).toHaveLength(1);
  expect(screen.getByTestId("connection-line")).toHaveAttribute("data-stroke", "#c084fc");
  const topology = screen.getByLabelText("Highlighted topology without geometry");
  expect(topology).toHaveTextContent("V-MOCK-1 ↔ Unnamed boundary");
  expect(topology).not.toHaveTextContent("mock-connection-without-geometry");
  expect(topology).toHaveTextContent("Connection geometry not recorded.");
});

test("a highlighted drawable connection retains its canvas line without a topology warning", () => {
  render(
    <DiagramViewer
      documentName="diagram.png" imageUrl="http://localhost:8000/files/page.png"
      page={{ id: "page-1", documentId: "doc-1", pageNumber: 1,
        imageUri: "/files/page.png", widthPx: 1600, heightPx: 800 }}
      graph={graph} selectedEntityId={null} selectedConnectionId={null}
      highlightedConnectionIds={["mock-connection-with-geometry"]}
      onSelectEntity={vi.fn()} onSelectConnection={vi.fn()} onClearSelection={vi.fn()}
    />,
  );

  expect(screen.getByTestId("connection-line")).toHaveAttribute("data-stroke", "#c084fc");
  expect(screen.queryByLabelText("Highlighted topology without geometry")).not.toBeInTheDocument();
});

test("keeps IDs and empty metadata out of the canvas footer", () => {
  const emptyMetadataGraph: EngineeringGraph = {
    ...graph,
    entities: graph.entities.map((entity, index) => index === 0
      ? { ...entity, id: "t019:entity:a310001b", tag: "None", displayName: " " }
      : entity),
  };
  render(
    <DiagramViewer
      documentName="diagram.png" imageUrl="http://localhost:8000/files/page.png"
      page={{ id: "page-1", documentId: "doc-1", pageNumber: 1,
        imageUri: "/files/page.png", widthPx: 1600, heightPx: 800 }}
      graph={emptyMetadataGraph} selectedEntityId="t019:entity:a310001b" selectedConnectionId={null}
      highlightedEntityIds={["t019:entity:a310001b"]} highlightedConnectionIds={[]}
      onSelectEntity={vi.fn()} onSelectConnection={vi.fn()} onClearSelection={vi.fn()}
    />,
  );

  expect(screen.queryByText("t019:entity:a310001b")).not.toBeInTheDocument();
  expect(screen.queryByText("None")).not.toBeInTheDocument();
  expect(screen.getByText("Unnamed equipment")).toBeInTheDocument();
  expect(screen.getByText("Drag to pan. Scroll or pinch to zoom.")).toHaveClass("viewer-help");
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
