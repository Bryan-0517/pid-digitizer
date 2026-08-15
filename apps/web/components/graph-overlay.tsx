import React from "react";
import { Group, Layer, Line, Rect, Text } from "react-konva";
import type { EngineeringEntity, EngineeringGraph } from "../types/engineering-graph";
import { normalizedBboxToImage, normalizedPointsToImage } from "./graph-geometry";

type GraphOverlayProps = {
  graph: EngineeringGraph;
  imageSize: { width: number; height: number };
  selectedEntityId: string | null;
  selectedConnectionId: string | null;
  showEntities: boolean;
  showConnections: boolean;
  viewScale: number;
  onSelectEntity: (entityId: string) => void;
  onSelectConnection: (connectionId: string) => void;
};

export function entityLabel(entity: EngineeringEntity): string {
  return entity.tag ?? entity.displayName ?? entity.id;
}

export default function GraphOverlay({
  graph,
  imageSize,
  selectedEntityId, selectedConnectionId,
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
          {graph.connections.map((connection) => connection.geometry?.polyline && (
            <Line
              key={connection.id}
              id={connection.id}
              points={normalizedPointsToImage(connection.geometry.polyline, imageSize)}
              stroke={connection.id === selectedConnectionId ? "#facc15" : "#38bdf8"}
              strokeWidth={connection.id === selectedConnectionId ? strokeWidth * 2 : strokeWidth}
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
          ))}
        </Layer>
      )}
      {showEntities && (
        <Layer name="entities">
          {graph.entities.map((entity) => {
            const bbox = entity.geometry?.bbox;
            if (!bbox) return null;
            const imageBox = normalizedBboxToImage(bbox, imageSize);
            const selected = entity.id === selectedEntityId;
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
                <Rect
                  {...imageBox}
                  fill={selected ? "rgba(250, 204, 21, 0.18)" : "rgba(14, 165, 233, 0.08)"}
                  stroke={selected ? "#facc15" : "#0ea5e9"}
                  strokeWidth={selected ? strokeWidth * 2 : strokeWidth}
                />
                <Text
                  x={imageBox.x}
                  y={Math.max(0, imageBox.y - fontSize * 1.3)}
                  text={entityLabel(entity)}
                  fontSize={fontSize}
                  fill={selected ? "#fef08a" : "#e0f2fe"}
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
