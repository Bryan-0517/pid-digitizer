import type { EngineeringConnection, EngineeringEntity, JsonValue } from "../types/engineering-graph";

export type UndoEntry = { documentId: string; objectType: "entity" | "connection"; objectId: string;
  endpoint: string; inversePatch: Record<string, JsonValue>; description: string };

export function entityUndoEntry(apiUrl: string, before: EngineeringEntity, after: EngineeringEntity): UndoEntry | null {
  const inversePatch: Record<string, JsonValue> = {};
  changed(inversePatch, "kind", before.kind, after.kind);
  changed(inversePatch, "subtype", before.subtype ?? null, after.subtype ?? null);
  changed(inversePatch, "tag", before.tag ?? null, after.tag ?? null);
  changed(inversePatch, "displayName", before.displayName ?? null, after.displayName ?? null);
  changed(inversePatch, "properties", before.properties, after.properties);
  if (before.assertion.reviewStatus !== after.assertion.reviewStatus) {
    inversePatch.assertion = { reviewStatus: before.assertion.reviewStatus };
  }
  if (Object.keys(inversePatch).length === 0) return null;
  return { documentId: before.documentId, objectType: "entity", objectId: before.id,
    endpoint: `${apiUrl}/entities/${before.id}`, description: `Undo last edit to ${before.tag ?? before.displayName ?? before.id}`,
    inversePatch };
}

export function connectionUndoEntry(apiUrl: string, before: EngineeringConnection,
  after: EngineeringConnection): UndoEntry | null {
  const inversePatch: Record<string, JsonValue> = {};
  changed(inversePatch, "sourceEntityId", before.sourceEntityId, after.sourceEntityId);
  changed(inversePatch, "targetEntityId", before.targetEntityId, after.targetEntityId);
  changed(inversePatch, "kind", before.kind, after.kind);
  changed(inversePatch, "medium", before.medium ?? null, after.medium ?? null);
  changed(inversePatch, "direction", before.direction ?? null, after.direction ?? null);
  changed(inversePatch, "properties", before.properties, after.properties);
  changed(inversePatch, "allowSelfLoop", before.allowSelfLoop ?? false, after.allowSelfLoop ?? false);
  if (before.assertion.reviewStatus !== after.assertion.reviewStatus) {
    inversePatch.assertion = { reviewStatus: before.assertion.reviewStatus };
  }
  if (Object.keys(inversePatch).length === 0) return null;
  return { documentId: before.documentId, objectType: "connection", objectId: before.id,
    endpoint: `${apiUrl}/connections/${before.id}`, description: `Undo last edit to connection ${before.id}`,
    inversePatch };
}

function changed(patch: Record<string, JsonValue>, key: string, before: JsonValue, after: JsonValue) {
  if (JSON.stringify(before) !== JSON.stringify(after)) patch[key] = before;
}
