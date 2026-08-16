import { expect, test } from "vitest";
import type { EngineeringConnection, EngineeringEntity } from "../types/engineering-graph";
import { connectionUndoEntry, entityUndoEntry } from "./undo-controller";

const entity: EngineeringEntity = { id: "e1", documentId: "d1", pageId: "p1", kind: "equipment",
  tag: "P-1", properties: { nested: { value: 2 } }, confidence: .8,
  assertion: { mode: "observed", reviewStatus: "confirmed" }, provenance: [],
  createdAt: "a", updatedAt: "b" };
const connection: EngineeringConnection = { id: "c1", documentId: "d1", sourceEntityId: "e1",
  targetEntityId: "e2", kind: "process", direction: "source_to_target", properties: { line: "1" },
  assertion: { mode: "human_added", reviewStatus: "corrected" }, provenance: [],
  createdAt: "a", updatedAt: "b" };

test("entity inverse PATCH contains only existing editable canonical fields", () => {
  const undo = entityUndoEntry("http://api", entity, { ...entity, tag: "P-2" })!;
  expect(undo.endpoint).toBe("http://api/entities/e1");
  expect(undo.inversePatch).toEqual({ tag: "P-1" });
  expect(undo.inversePatch).not.toHaveProperty("confidence");
});

test("connection inverse PATCH excludes create/delete and preserves editable prior values", () => {
  const undo = connectionUndoEntry("http://api", connection,
    { ...connection, direction: "target_to_source" })!;
  expect(undo.endpoint).toBe("http://api/connections/c1");
  expect(undo.inversePatch).toEqual({ direction: "source_to_target" });
});

test("unchanged persisted responses do not create an undo entry", () => {
  expect(entityUndoEntry("http://api", entity, entity)).toBeNull();
});
