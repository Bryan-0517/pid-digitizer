import React from "react";
import { Group, Layer, Line, Rect, Text } from "react-konva";
import type { EngineeringEntity, EngineeringGraph } from "../types/engineering-graph";
import { normalizedBboxToImage, normalizedPointsToImage } from "./graph-geometry";

type GraphOverlayProps = {
  graph: EngineeringGraph;
  imageSize: { width: number; height: number };
  selectedEntityId: string | null;
  selectedConnectionId: string | null;
  highlightedEntityIds: string[];
  highlightedConnectionIds: string[];
  showEntities: boolean;
  showConnections: boolean;
  viewScale: number;
  onSelectEntity: (entityId: string) => void;
  onSelectConnection: (connectionId: string) => void;
};

export function entityLabel(entity: EngineeringEntity): string {
  const tag = visibleLabel(entity.tag);
  const displayName = visibleLabel(entity.displayName);
  return tag ?? displayName ?? `Unnamed ${entity.kind}`;
}

function visibleLabel(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed && trimmed.toLowerCase() !== "none" ? trimmed : null;
}

export default function GraphOverlay({
  graph,
  imageSize,
  selectedEntityId, selectedConnectionId,
  highlightedEntityIds, highlightedConnectionIds,
  showEntities,
  showConnections,
  viewScale,
  onSelectEntity, onSelectConnection,
}: GraphOverlayProps) {
  const strokeWidth = 2 / viewScale;
  const fontSize = 14 / viewScale;

  return (
    <>
      {showConnections && (
        <Layer name="connections">
          {graph.connections.map((connection) => connection.geometry?.polyline && (() => {
            const selected = connection.id === selectedConnectionId;
            const highlighted = highlightedConnectionIds.includes(connection.id);
            return (
            <Line
              key={connection.id}
              id={connection.id}
              points={normalizedPointsToImage(connection.geometry.polyline, imageSize)}
              stroke={selected ? "#facc15" : highlighted ? "#c084fc" : "#38bdf8"}
              strokeWidth={selected || highlighted ? strokeWidth * 2 : strokeWidth}
              lineCap="round"
              lineJoin="round"
              hitStrokeWidth={12 / viewScale}
              onClick={(event) => {
                event.cancelBubble = true;
                onSelectConnection(connection.id);
              }}
              onTap={(event) => {
                event.cancelBubble = true;
                onSelectConnection(connection.id);
              }}
            />
            );
          })())}
        </Layer>
      )}
      {showEntities && (
        <Layer name="entities">
          {graph.entities.map((entity) => {
            const bbox = entity.geometry?.bbox;
            if (!bbox) return null;
            const imageBox = normalizedBboxToImage(bbox, imageSize);
            const selected = entity.id === selectedEntityId;
            const highlighted = highlightedEntityIds.includes(entity.id);
            return (
              <Group
                key={entity.id}
                id={entity.id}
                onClick={(event) => {
                  event.cancelBubble = true;
                  onSelectEntity(entity.id);
                }}
                onTap={(event) => {
                  event.cancelBubble = true;
                  onSelectEntity(entity.id);
                }}
              >
                {highlighted && (
                  <Rect
                    {...imageBox}
                    name="entity-highlight-halo"
                    fill="rgba(0, 0, 0, 0)"
                    stroke="#f5d0fe"
                    strokeWidth={6 / viewScale}
                    shadowColor="#d946ef"
                    shadowBlur={14 / viewScale}
                    shadowOpacity={0.95}
                    listening={false}
                  />
                )}
                <Rect
                  {...imageBox}
                  fill={selected ? "rgba(250, 204, 21, 0.18)" : highlighted ? "rgba(192, 132, 252, 0.18)" : "rgba(14, 165, 233, 0.08)"}
                  stroke={selected ? "#facc15" : highlighted ? "#c084fc" : "#0ea5e9"}
                  strokeWidth={selected ? strokeWidth * 2 : highlighted ? strokeWidth * 3 : strokeWidth}
                />
                <Text
                  x={imageBox.x}
                  y={Math.max(0, imageBox.y - fontSize * 1.3)}
                  text={entityLabel(entity)}
                  fontSize={fontSize}
                  fill={selected ? "#fef08a" : highlighted ? "#e9d5ff" : "#e0f2fe"}
                  stroke="#111827"
                  strokeWidth={0.75 / viewScale}
                />
              </Group>
            );
          })}
        </Layer>
      )}
    </>
  );
}
