import { useEffect, useMemo, useState } from "react";

import { OfficeGrid } from "./OfficeGrid";
import {
  FIXTURE_OPTIONS,
  FLOOR_OPTIONS,
  cloneLayout,
  parseOfficeLayout,
  serializeOfficeLayout,
  type FixtureKind,
  type FloorKind,
  type OfficeLayout,
} from "./officeLayout";
import type { CharacterState } from "../types";

type EditorTool = "brush" | "eraser" | "select";
type PaintTarget = "floor" | "fixture" | "agent";

interface OfficeEditorProps {
  characterState: CharacterState;
  lastTool: string | null;
  tileSize: number;
  layout: OfficeLayout;
  onChange: (layout: OfficeLayout) => void;
  onReset: () => void;
}

const TOOL_OPTIONS: Array<{ value: EditorTool; label: string }> = [
  { value: "brush", label: "Brush" },
  { value: "eraser", label: "Eraser" },
  { value: "select", label: "Select" },
];

const TARGET_OPTIONS: Array<{ value: PaintTarget; label: string }> = [
  { value: "floor", label: "Floor" },
  { value: "fixture", label: "Fixture" },
  { value: "agent", label: "Agent" },
];

export function OfficeEditor({
  characterState,
  lastTool,
  tileSize,
  layout,
  onChange,
  onReset,
}: OfficeEditorProps) {
  const [tool, setTool] = useState<EditorTool>("brush");
  const [target, setTarget] = useState<PaintTarget>("fixture");
  const [selectedFloor, setSelectedFloor] = useState<FloorKind>("wood");
  const [selectedFixture, setSelectedFixture] = useState<FixtureKind>("plant");
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number } | null>(null);
  const [jsonDraft, setJsonDraft] = useState(() => serializeOfficeLayout(layout));
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [isPainting, setIsPainting] = useState(false);

  useEffect(() => {
    const stopPainting = () => setIsPainting(false);
    window.addEventListener("pointerup", stopPainting);
    return () => window.removeEventListener("pointerup", stopPainting);
  }, []);

  const selectedCellData = useMemo(() => {
    if (!selectedCell) {
      return null;
    }
    return layout.cells[selectedCell.row]?.[selectedCell.col] ?? null;
  }, [layout, selectedCell]);

  function updateLayout(mutator: (draft: OfficeLayout) => void) {
    const next = cloneLayout(layout);
    mutator(next);
    onChange(next);
  }

  function selectTile(row: number, col: number) {
    const cell = layout.cells[row]?.[col];
    if (!cell) {
      return;
    }

    setSelectedCell({ row, col });
    setSelectedFloor(cell.floor);
    if (cell.fixture) {
      setSelectedFixture(cell.fixture);
    }
  }

  function applyTool(row: number, col: number) {
    if (!layout.cells[row]?.[col]) {
      return;
    }

    if (tool === "select") {
      selectTile(row, col);
      return;
    }

    updateLayout((draft) => {
      if (target === "agent") {
        draft.agent = { row, col };
        return;
      }

      const cell = draft.cells[row][col];
      if (tool === "eraser") {
        if (target === "floor") {
          draft.cells[row][col] = { ...cell, floor: "wood" };
          return;
        }
        draft.cells[row][col] = { ...cell, fixture: undefined };
        return;
      }

      if (target === "floor") {
        draft.cells[row][col] = { ...cell, floor: selectedFloor };
        return;
      }

      draft.cells[row][col] = { ...cell, fixture: selectedFixture };
    });
  }

  function handleTilePointerDown(row: number, col: number) {
    setIsPainting(true);
    applyTool(row, col);
  }

  function handleTilePointerEnter(row: number, col: number) {
    if (!isPainting || tool === "select") {
      return;
    }
    applyTool(row, col);
  }

  function handleTileClick(row: number, col: number) {
    if (tool === "select") {
      selectTile(row, col);
    }
  }

  function handleExportJson() {
    setJsonDraft(serializeOfficeLayout(layout));
    setJsonError(null);
  }

  function handleLoadJson() {
    try {
      const parsed = parseOfficeLayout(jsonDraft);
      onChange(parsed);
      setSelectedCell(null);
      setJsonError(null);
    } catch (error) {
      setJsonError(error instanceof Error ? error.message : "Invalid JSON.");
    }
  }

  function handleReset() {
    setSelectedCell(null);
    setJsonError(null);
    onReset();
  }

  return (
    <section className="editor-shell">
      <div className="editor-header">
        <div>
          <h2>Layout Editor</h2>
          <p>Paint tiles, erase props, inspect cells and save or load the office as JSON.</p>
        </div>
        <div className="editor-actions">
          <button type="button" onClick={handleExportJson}>
            Export JSON
          </button>
          <button type="button" onClick={handleLoadJson}>
            Load JSON
          </button>
          <button type="button" onClick={handleReset}>
            Reset Layout
          </button>
        </div>
      </div>

      <div className="editor-layout">
        <div className="editor-stage">
          <OfficeGrid
            characterState={characterState}
            lastTool={lastTool}
            layout={layout}
            tileSize={tileSize}
            selectedCell={selectedCell}
            interactive
            onTilePointerDown={handleTilePointerDown}
            onTilePointerEnter={handleTilePointerEnter}
            onTileClick={handleTileClick}
          />
        </div>

        <aside className="editor-sidebar">
          <div className="editor-panel">
            <h3>Tools</h3>
            <div className="chip-grid">
              {TOOL_OPTIONS.map((entry) => (
                <button
                  key={entry.value}
                  type="button"
                  className={tool === entry.value ? "chip chip--active" : "chip"}
                  onClick={() => setTool(entry.value)}
                >
                  {entry.label}
                </button>
              ))}
            </div>
          </div>

          <div className="editor-panel">
            <h3>Target</h3>
            <div className="chip-grid">
              {TARGET_OPTIONS.map((entry) => (
                <button
                  key={entry.value}
                  type="button"
                  className={target === entry.value ? "chip chip--active" : "chip"}
                  onClick={() => setTarget(entry.value)}
                >
                  {entry.label}
                </button>
              ))}
            </div>
          </div>

          <div className="editor-panel">
            <h3>Floors</h3>
            <div className="swatch-grid">
              {FLOOR_OPTIONS.map((entry) => (
                <button
                  key={entry.value}
                  type="button"
                  className={selectedFloor === entry.value ? "swatch swatch--active" : "swatch"}
                  onClick={() => {
                    setSelectedFloor(entry.value);
                    setTarget("floor");
                    setTool("brush");
                  }}
                >
                  <span
                    className="swatch-color"
                    style={{ backgroundColor: entry.swatch }}
                  />
                  <span>{entry.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="editor-panel">
            <h3>Fixtures</h3>
            <div className="swatch-grid">
              {FIXTURE_OPTIONS.map((entry) => (
                <button
                  key={entry.value}
                  type="button"
                  className={selectedFixture === entry.value ? "swatch swatch--active" : "swatch"}
                  onClick={() => {
                    setSelectedFixture(entry.value);
                    setTarget("fixture");
                    setTool("brush");
                  }}
                >
                  <span
                    className="swatch-color"
                    style={{ backgroundColor: entry.swatch }}
                  />
                  <span>{entry.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="editor-panel">
            <h3>Selection</h3>
            {selectedCell && selectedCellData ? (
              <div className="selection-card">
                <span>{`Tile ${selectedCell.col}, ${selectedCell.row}`}</span>
                <span>{`Floor: ${selectedCellData.floor}`}</span>
                <span>{`Fixture: ${selectedCellData.fixture ?? "none"}`}</span>
                <span>
                  {layout.agent.col === selectedCell.col && layout.agent.row === selectedCell.row
                    ? "Agent: here"
                    : "Agent: elsewhere"}
                </span>
              </div>
            ) : (
              <p className="selection-placeholder">Use Select to inspect a tile.</p>
            )}
          </div>

          <div className="editor-panel">
            <h3>JSON</h3>
            <textarea
              className="json-editor"
              value={jsonDraft}
              onChange={(event) => setJsonDraft(event.target.value)}
              spellCheck={false}
            />
            {jsonError ? <p className="json-error">{jsonError}</p> : null}
          </div>
        </aside>
      </div>
    </section>
  );
}
