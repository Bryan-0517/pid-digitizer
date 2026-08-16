"use client";

import Konva from "konva";
import React from "react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Image as KonvaImage, Layer, Stage } from "react-konva";
import type { DocumentPage, EngineeringGraph } from "../types/engineering-graph";
import GraphOverlay, { entityLabel } from "./graph-overlay";
import { fitTransform, Point, ViewTransform, zoomAtPoint } from "./view-transform";

type DiagramViewerProps = {
  page: DocumentPage;
  imageUrl: string;
  documentName: string;
  graph: EngineeringGraph;
  selectedEntityId: string | null;
  selectedConnectionId: string | null;
  highlightedEntityIds?: string[];
  highlightedConnectionIds?: string[];
  onSelectEntity: (entityId: string | null) => void;
  onSelectConnection: (connectionId: string | null) => void;
  onClearSelection: () => void;
};

type Size = { width: number; height: number };

const INITIAL_VIEW: ViewTransform = { x: 0, y: 0, scale: 1 };
const WHEEL_SCALE = 1.08;

export default function DiagramViewer({
  page, imageUrl, documentName, graph, selectedEntityId, selectedConnectionId,
  highlightedEntityIds = [], highlightedConnectionIds = [],
  onSelectEntity, onSelectConnection, onClearSelection,
}: DiagramViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<Konva.Stage>(null);
  const lastPinchRef = useRef<{ center: Point; distance: number } | null>(null);
  const [containerSize, setContainerSize] = useState<Size>({ width: 0, height: 0 });
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [imageError, setImageError] = useState(false);
  const [imageLoading, setImageLoading] = useState(true);
  const [view, setView] = useState<ViewTransform>(INITIAL_VIEW);
  const [fitMode, setFitMode] = useState(true);
  const [showEntities, setShowEntities] = useState(true);
  const [showConnections, setShowConnections] = useState(true);
  const entitiesById = new Map(graph.entities.map((entity) => [entity.id, entity]));
  const highlightedConnectionsWithoutGeometry = graph.connections.filter((connection) =>
    highlightedConnectionIds.includes(connection.id) && !connection.geometry?.polyline,
  );

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.round(entry.contentRect.width);
      const height = Math.round(entry.contentRect.height);
      setContainerSize({ width, height });
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let active = true;
    setImageLoading(true);
    setImageError(false);
    setImage(null);
    const nextImage = new window.Image();
    nextImage.onload = () => {
      if (active) {
        setImage(nextImage);
        setImageError(false);
        setImageLoading(false);
      }
    };
    nextImage.onerror = () => {
      if (active) { setImageError(true); setImageLoading(false); }
    };
    nextImage.src = imageUrl;
    return () => {
      active = false;
    };
  }, [imageUrl]);

  const fitToScreen = useCallback(() => {
    setView(fitTransform(containerSize, { width: page.widthPx, height: page.heightPx }));
    setFitMode(true);
  }, [containerSize, page.heightPx, page.widthPx]);

  useEffect(() => {
    if (fitMode && containerSize.width > 0 && containerSize.height > 0) fitToScreen();
  }, [containerSize, fitMode, fitToScreen, page.id]);

  function handleWheel(event: Konva.KonvaEventObject<WheelEvent>) {
    event.evt.preventDefault();
    const pointer = stageRef.current?.getPointerPosition();
    if (!pointer) return;
    const factor = event.evt.deltaY > 0 ? 1 / WHEEL_SCALE : WHEEL_SCALE;
    setView((current) => zoomAtPoint(current, pointer, current.scale * factor));
    setFitMode(false);
  }

  function handleTouchMove(event: Konva.KonvaEventObject<TouchEvent>) {
    const touches = event.evt.touches;
    if (touches.length !== 2) return;
    event.evt.preventDefault();
    stageRef.current?.stopDrag();
    const bounds = containerRef.current?.getBoundingClientRect();
    if (!bounds) return;
    const first = { x: touches[0].clientX - bounds.left, y: touches[0].clientY - bounds.top };
    const second = { x: touches[1].clientX - bounds.left, y: touches[1].clientY - bounds.top };
    const center = { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 };
    const distance = Math.hypot(second.x - first.x, second.y - first.y);
    const previous = lastPinchRef.current;
    if (previous && previous.distance > 0) {
      setView((current) => {
        const centered = zoomAtPoint(
          current,
          previous.center,
          current.scale * (distance / previous.distance),
        );
        return {
          ...centered,
          x: centered.x + center.x - previous.center.x,
          y: centered.y + center.y - previous.center.y,
        };
      });
      setFitMode(false);
    }
    lastPinchRef.current = { center, distance };
  }

  return (
    <div className="diagram-viewer">
      <div className="viewer-toolbar" aria-label="Diagram view controls">
        <button type="button" onClick={fitToScreen}>Fit to screen</button>
        <output aria-label="Zoom level">{Math.round(view.scale * 100)}%</output>
        <label><input type="checkbox" checked={showEntities} onChange={(event) => setShowEntities(event.target.checked)} /> Entities</label>
        <label><input type="checkbox" checked={showConnections} onChange={(event) => setShowConnections(event.target.checked)} /> Connections</label>
        {graph.entities.some((entity) => entity.provenance.some(
          (evidence) => evidence.sourceRef === "t004-mock-fixture",
        )) && <span className="mock-notice">Mock overlay — unreviewed</span>}
      </div>
      <div
        ref={containerRef}
        className="canvas-container"
        data-testid="diagram-viewer"
        role="img"
        aria-label={`Interactive page 1 of ${documentName}`}
      >
        {containerSize.width > 0 && containerSize.height > 0 && (
          <Stage
            ref={stageRef}
            width={containerSize.width}
            height={containerSize.height}
            x={view.x}
            y={view.y}
            scaleX={view.scale}
            scaleY={view.scale}
            draggable
            onDragStart={() => setFitMode(false)}
            onDragEnd={(event) => {
              setView((current) => ({ ...current, x: event.target.x(), y: event.target.y() }));
            }}
            onWheel={handleWheel}
            onTouchMove={handleTouchMove}
            onTouchEnd={() => { lastPinchRef.current = null; }}
            onClick={(event) => {
              if (event.target === event.target.getStage()) onClearSelection();
            }}
            onTap={(event) => {
              if (event.target === event.target.getStage()) onClearSelection();
            }}
          >
            <Layer listening={false}>
              {image && (
                <KonvaImage
                  image={image}
                  width={page.widthPx}
                  height={page.heightPx}
                  listening={false}
                  perfectDrawEnabled={false}
                />
              )}
            </Layer>
            <GraphOverlay
              graph={graph}
              imageSize={{ width: page.widthPx, height: page.heightPx }}
              selectedEntityId={selectedEntityId}
              selectedConnectionId={selectedConnectionId}
              highlightedEntityIds={highlightedEntityIds}
              highlightedConnectionIds={highlightedConnectionIds}
              showEntities={showEntities}
              showConnections={showConnections}
              viewScale={view.scale}
              onSelectEntity={onSelectEntity}
              onSelectConnection={onSelectConnection}
            />
          </Stage>
        )}
        {imageError && <p className="viewer-error" role="alert">Page image could not be loaded.</p>}
        {imageLoading && <p className="viewer-status" role="status">Loading page image…</p>}
      </div>
      <output aria-label="Selected entity">{selectedEntityId ?? "None"}</output>
      <output aria-label="Selected connection">{selectedConnectionId ?? "None"}</output>
      <output aria-label="Highlighted entities">{highlightedEntityIds.join(", ") || "None"}</output>
      <output aria-label="Highlighted connections">{highlightedConnectionIds.join(", ") || "None"}</output>
      {highlightedConnectionsWithoutGeometry.length > 0 && (
        <section className="highlighted-topology" aria-label="Highlighted topology without geometry">
          <h3>Highlighted topology</h3>
          {highlightedConnectionsWithoutGeometry.map((connection) => {
            const source = entitiesById.get(connection.sourceEntityId);
            const target = entitiesById.get(connection.targetEntityId);
            return (
              <div key={connection.id} className="highlighted-topology-item">
                <strong>{source ? entityLabel(source) : connection.sourceEntityId} ↔ {target ? entityLabel(target) : connection.targetEntityId}</strong>
                <span>Canonical connection: <code>{connection.id}</code></span>
                <span>Connection geometry not recorded.</span>
              </div>
            );
          })}
        </section>
      )}
      <p className="viewer-help">Drag to pan. Scroll or pinch to zoom.</p>
    </div>
  );
}
