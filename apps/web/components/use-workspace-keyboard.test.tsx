import { cleanup, fireEvent, render } from "@testing-library/react";
import React, { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { useWorkspaceKeyboard } from "./use-workspace-keyboard";

afterEach(cleanup);

function Harness({ onDelete = vi.fn() }: { onDelete?: () => void }) {
  const [selection, setSelection] = useState(true);
  const [highlights, setHighlights] = useState(true);
  useWorkspaceKeyboard({ documentId: "doc", hasSelection: selection, hasHighlights: highlights,
    onEscapeSelection: () => setSelection(false), onEscapeHighlights: () => setHighlights(false),
    onDeleteConnection: onDelete });
  return <><output data-testid="state">{`${selection}-${highlights}`}</output><input aria-label="Editable" />
    <div role="textbox" contentEditable aria-label="Rich editable" /></>;
}

test("Escape clears selection before highlights and never invokes deletion", () => {
  const onDelete = vi.fn();
  const view = render(<Harness onDelete={onDelete} />);
  fireEvent.keyDown(window, { key: "Escape" });
  expect(view.getByTestId("state")).toHaveTextContent("false-true");
  fireEvent.keyDown(window, { key: "Escape" });
  expect(view.getByTestId("state")).toHaveTextContent("false-false");
  expect(onDelete).not.toHaveBeenCalled();
});

test("Delete and Escape are ignored in editable controls", () => {
  const onDelete = vi.fn();
  const view = render(<Harness onDelete={onDelete} />);
  fireEvent.keyDown(view.getByLabelText("Editable"), { key: "Delete" });
  fireEvent.keyDown(view.getByLabelText("Editable"), { key: "Escape" });
  fireEvent.keyDown(view.getByLabelText("Rich editable"), { key: "Delete" });
  expect(view.getByTestId("state")).toHaveTextContent("true-true");
  expect(onDelete).not.toHaveBeenCalled();
});
