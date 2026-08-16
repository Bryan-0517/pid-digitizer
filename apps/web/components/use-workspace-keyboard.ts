"use client";
import { useEffect } from "react";

export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
    || target.closest("[contenteditable]:not([contenteditable='false']), [role='textbox']") !== null;
}

export function useWorkspaceKeyboard(options: { documentId: string | null; hasSelection: boolean;
  hasHighlights: boolean; onEscapeSelection: () => void; onEscapeHighlights: () => void;
  onDeleteConnection: () => void }) {
  const { documentId, hasSelection, hasHighlights, onEscapeSelection, onEscapeHighlights,
    onDeleteConnection } = options;
  useEffect(() => {
    if (!documentId) return;
    function keydown(event: KeyboardEvent) {
      if (isEditableTarget(event.target)) return;
      if (event.key === "Escape" && hasSelection) { event.preventDefault(); onEscapeSelection(); }
      else if (event.key === "Escape" && hasHighlights) { event.preventDefault(); onEscapeHighlights(); }
      else if (event.key === "Delete") onDeleteConnection();
    }
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, [documentId, hasHighlights, hasSelection, onDeleteConnection, onEscapeHighlights, onEscapeSelection]);
}
