import { useMemo, type CSSProperties } from "react";

import type { CharacterState, OfficeSubagent } from "../types";
import { BrainBaby } from "./BrainBaby";

type FloorKind = "wood" | "carpet" | "tile" | "concrete";
type FixtureKind =
  | "wall"
  | "window"
  | "door"
  | "desk-left"
  | "desk-mid"
  | "desk-right"
  | "chair"
  | "shelf"
  | "plant"
  | "frame"
  | "sofa-left"
  | "sofa-right"
  | "cabinet"
  | "server"
  | "whiteboard"
  | "coffee"
  | "table"
  | "lamp";

interface Cell {
  floor: FloorKind;
  fixture?: FixtureKind;
}

interface OfficeLayout {
  cells: Cell[][];
  agent: {
    col: number;
    row: number;
  };
}

interface OfficeGridProps {
  characterState: CharacterState;
  lastTool: string | null;
  subagents?: OfficeSubagent[];
  layout?: OfficeLayout;
  cols?: number;
  rows?: number;
  tileSize?: number;
  selectedCell?: { row: number; col: number } | null;
  interactive?: boolean;
  onTilePointerDown?: (row: number, col: number) => void;
  onTilePointerEnter?: (row: number, col: number) => void;
  onTileClick?: (row: number, col: number) => void;
}

const DEFAULT_COLS = 32;
const DEFAULT_ROWS = 24;
const DEFAULT_TILE_SIZE = 24;

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function createCells(cols: number, rows: number): Cell[][] {
  return Array.from({ length: rows }, () =>
    Array.from({ length: cols }, () => ({ floor: "wood" as FloorKind }))
  );
}

function fillFloorRect(
  cells: Cell[][],
  x: number,
  y: number,
  width: number,
  height: number,
  floor: FloorKind
) {
  for (let row = y; row < y + height; row += 1) {
    for (let col = x; col < x + width; col += 1) {
      if (cells[row]?.[col]) {
        cells[row][col] = { ...cells[row][col], floor };
      }
    }
  }
}

function setFixture(cells: Cell[][], x: number, y: number, fixture: FixtureKind) {
  if (cells[y]?.[x]) {
    cells[y][x] = { ...cells[y][x], fixture };
  }
}

function placeDeskRow(cells: Cell[][], x: number, y: number, width: number) {
  for (let index = 0; index < width; index += 1) {
    if (index === 0) {
      setFixture(cells, x + index, y, "desk-left");
    } else if (index === width - 1) {
      setFixture(cells, x + index, y, "desk-right");
    } else {
      setFixture(cells, x + index, y, "desk-mid");
    }
  }
}

function paintRoomWalls(
  cells: Cell[][],
  x: number,
  y: number,
  width: number,
  height: number,
  doorPosition?: { x: number; y: number }
) {
  for (let col = x; col < x + width; col += 1) {
    setFixture(cells, col, y, "wall");
    setFixture(cells, col, y + height - 1, "wall");
  }
  for (let row = y; row < y + height; row += 1) {
    setFixture(cells, x, row, "wall");
    setFixture(cells, x + width - 1, row, "wall");
  }
  if (doorPosition) {
    setFixture(cells, doorPosition.x, doorPosition.y, "door");
  }
}

function buildOfficeLayout(cols: number, rows: number): OfficeLayout {
  const cells = createCells(cols, rows);

  for (let col = 0; col < cols; col += 1) {
    setFixture(cells, col, 0, "wall");
    setFixture(cells, col, rows - 1, "wall");
  }
  for (let row = 0; row < rows; row += 1) {
    setFixture(cells, 0, row, "wall");
    setFixture(cells, cols - 1, row, "wall");
  }

  for (let col = 3; col < cols - 3; col += 5) {
    setFixture(cells, col, 0, "window");
  }
  for (let row = 4; row < rows - 4; row += 6) {
    setFixture(cells, cols - 1, row, "window");
  }
  setFixture(cells, Math.floor(cols / 2), rows - 1, "door");

  fillFloorRect(cells, Math.floor(cols / 2) - 2, rows - 3, 5, 2, "concrete");

  const library = {
    x: 2,
    y: 2,
    w: clamp(Math.floor(cols * 0.24), 7, 10),
    h: clamp(Math.floor(rows * 0.22), 6, 8),
  };
  fillFloorRect(cells, library.x, library.y, library.w, library.h, "carpet");
  for (let col = library.x + 1; col < library.x + library.w - 1; col += 1) {
    setFixture(cells, col, library.y, "shelf");
  }
  for (let row = library.y + 1; row < library.y + library.h - 1; row += 1) {
    setFixture(cells, library.x, row, "shelf");
  }
  setFixture(cells, library.x + library.w - 2, library.y + 1, "plant");
  setFixture(cells, library.x + library.w - 3, library.y + 3, "table");
  setFixture(cells, library.x + library.w - 3, library.y + 4, "lamp");
  setFixture(cells, library.x + 2, library.y + library.h - 1, "frame");
  setFixture(cells, library.x + 4, library.y + library.h - 1, "frame");

  const meeting: { x: number; y: number; w: number; h: number } = {
    w: clamp(Math.floor(cols * 0.22), 8, 11),
    h: clamp(Math.floor(rows * 0.22), 6, 8),
    x: 0,
    y: 0,
  };
  meeting.x = cols - meeting.w - 3;
  meeting.y = 2;
  fillFloorRect(cells, meeting.x + 1, meeting.y + 1, meeting.w - 2, meeting.h - 2, "tile");
  paintRoomWalls(cells, meeting.x, meeting.y, meeting.w, meeting.h, {
    x: meeting.x,
    y: meeting.y + Math.floor(meeting.h / 2),
  });
  for (let col = meeting.x + 2; col < meeting.x + meeting.w - 2; col += 1) {
    setFixture(cells, col, meeting.y + 1, "whiteboard");
  }
  setFixture(cells, meeting.x + 2, meeting.y + meeting.h - 2, "plant");
  setFixture(cells, meeting.x + meeting.w - 3, meeting.y + meeting.h - 2, "plant");
  setFixture(cells, meeting.x + Math.floor(meeting.w / 2), meeting.y + 3, "table");
  setFixture(cells, meeting.x + Math.floor(meeting.w / 2), meeting.y + 4, "chair");
  setFixture(cells, meeting.x + Math.floor(meeting.w / 2) - 1, meeting.y + 4, "chair");
  setFixture(cells, meeting.x + Math.floor(meeting.w / 2) + 1, meeting.y + 4, "chair");

  const lounge: { x: number; y: number; w: number; h: number } = {
    x: 2,
    h: clamp(Math.floor(rows * 0.2), 5, 7),
    w: clamp(Math.floor(cols * 0.24), 7, 10),
    y: 0,
  };
  lounge.y = rows - lounge.h - 3;
  fillFloorRect(cells, lounge.x, lounge.y, lounge.w, lounge.h, "carpet");
  setFixture(cells, lounge.x + 1, lounge.y + 1, "sofa-left");
  setFixture(cells, lounge.x + 2, lounge.y + 1, "sofa-right");
  setFixture(cells, lounge.x + 4, lounge.y + 2, "table");
  setFixture(cells, lounge.x + 5, lounge.y + 1, "plant");
  setFixture(cells, lounge.x + 2, lounge.y + lounge.h - 1, "frame");
  setFixture(cells, lounge.x + 4, lounge.y + lounge.h - 1, "frame");

  const lab: { x: number; y: number; w: number; h: number } = {
    w: clamp(Math.floor(cols * 0.22), 8, 10),
    h: clamp(Math.floor(rows * 0.22), 5, 7),
    x: 0,
    y: 0,
  };
  lab.x = cols - lab.w - 3;
  lab.y = rows - lab.h - 3;
  fillFloorRect(cells, lab.x, lab.y, lab.w, lab.h, "tile");
  for (let col = lab.x + 1; col < lab.x + lab.w - 2; col += 1) {
    setFixture(cells, col, lab.y, "cabinet");
  }
  for (let row = lab.y + 1; row < lab.y + lab.h - 1; row += 1) {
    setFixture(cells, lab.x + lab.w - 1, row, "server");
  }
  setFixture(cells, lab.x + 1, lab.y + 2, "coffee");
  setFixture(cells, lab.x + 3, lab.y + 2, "cabinet");
  setFixture(cells, lab.x + 1, lab.y + lab.h - 1, "plant");

  const workspaceY = clamp(Math.floor(rows * 0.48), 9, rows - 9);
  const leftBankX = clamp(Math.floor(cols * 0.32), 7, cols - 16);
  const bankWidth = clamp(Math.floor(cols * 0.14), 3, 4);
  const rightBankX = clamp(leftBankX + bankWidth + 3, 12, cols - 7);

  placeDeskRow(cells, leftBankX, workspaceY, bankWidth);
  placeDeskRow(cells, rightBankX, workspaceY, bankWidth);
  placeDeskRow(cells, leftBankX, workspaceY + 4, bankWidth);
  placeDeskRow(cells, rightBankX, workspaceY + 4, bankWidth);

  for (let index = 0; index < bankWidth; index += 1) {
    setFixture(cells, leftBankX + index, workspaceY + 1, "chair");
    setFixture(cells, rightBankX + index, workspaceY + 1, "chair");
    setFixture(cells, leftBankX + index, workspaceY + 5, "chair");
    setFixture(cells, rightBankX + index, workspaceY + 5, "chair");
  }

  setFixture(cells, leftBankX - 2, workspaceY, "plant");
  setFixture(cells, rightBankX + bankWidth + 1, workspaceY + 4, "plant");
  setFixture(cells, leftBankX + bankWidth + 1, workspaceY + 2, "lamp");
  setFixture(cells, rightBankX - 2, workspaceY + 6, "lamp");

  const galleryY = clamp(Math.floor(rows * 0.35), 7, rows - 8);
  for (let offset = 0; offset < 3; offset += 1) {
    setFixture(cells, Math.floor(cols / 2) - 2 + offset * 2, galleryY, "frame");
  }

  return {
    cells,
    agent: {
      col: leftBankX + 1,
      row: workspaceY + 2,
    },
  };
}

function getFloorStyle(floor: FloorKind, row: number, col: number): CSSProperties {
  if (floor === "wood") {
    const base = (row + col) % 2 === 0 ? "#88603d" : "#7a5536";
    return {
      backgroundColor: base,
      backgroundImage: [
        "linear-gradient(90deg, rgba(255,255,255,0.08) 0 8%, transparent 8% 92%, rgba(0,0,0,0.1) 92% 100%)",
        "linear-gradient(180deg, rgba(255,255,255,0.06) 0 18%, rgba(0,0,0,0.12) 100%)",
      ].join(","),
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08), inset 0 -2px 0 rgba(0,0,0,0.18)",
    };
  }

  if (floor === "carpet") {
    const base = (row + col) % 2 === 0 ? "#48516b" : "#414864";
    return {
      backgroundColor: base,
      backgroundImage: [
        "repeating-linear-gradient(0deg, rgba(255,255,255,0.06) 0 2px, transparent 2px 4px)",
        "repeating-linear-gradient(90deg, rgba(0,0,0,0.08) 0 2px, transparent 2px 4px)",
      ].join(","),
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04), inset 0 -2px 0 rgba(0,0,0,0.18)",
    };
  }

  if (floor === "tile") {
    return {
      backgroundColor: "#aeb7c4",
      backgroundImage: [
        "repeating-linear-gradient(0deg, rgba(255,255,255,0.35) 0 1px, transparent 1px 12px)",
        "repeating-linear-gradient(90deg, rgba(255,255,255,0.35) 0 1px, transparent 1px 12px)",
        "linear-gradient(180deg, rgba(255,255,255,0.15), rgba(0,0,0,0.1))",
      ].join(","),
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.12), inset 0 -2px 0 rgba(0,0,0,0.12)",
    };
  }

  return {
    backgroundColor: "#5f6572",
    backgroundImage: [
      "radial-gradient(circle at 6px 6px, rgba(255,255,255,0.16) 0 1px, transparent 1px 100%)",
      "radial-gradient(circle at 14px 10px, rgba(0,0,0,0.16) 0 1px, transparent 1px 100%)",
      "linear-gradient(180deg, rgba(255,255,255,0.04), rgba(0,0,0,0.18))",
    ].join(","),
    boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05), inset 0 -2px 0 rgba(0,0,0,0.24)",
  };
}

function isStructuralFixture(fixture?: FixtureKind) {
  return fixture === "wall" || fixture === "window" || fixture === "door";
}

function getFixtureStyle(
  fixture: FixtureKind,
  neighbors: { north: boolean; south: boolean; east: boolean; west: boolean }
): CSSProperties {
  if (fixture === "wall") {
    return {
      backgroundColor: "#d4be9a",
      backgroundImage:
        "linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.02) 45%, rgba(0,0,0,0.12) 100%)",
      boxShadow: [
        neighbors.north ? "" : "inset 0 3px 0 #f0dfc1",
        neighbors.south ? "" : "inset 0 -4px 0 #8e6d50",
        neighbors.west ? "" : "inset 3px 0 0 rgba(86, 63, 42, 0.35)",
        neighbors.east ? "" : "inset -3px 0 0 rgba(86, 63, 42, 0.35)",
      ]
        .filter(Boolean)
        .join(", "),
    };
  }

  if (fixture === "window") {
    return {
      backgroundColor: "#8cc6ff",
      backgroundImage: [
        "linear-gradient(90deg, #2d4668 0 3px, transparent 3px calc(100% - 3px), #2d4668 calc(100% - 3px) 100%)",
        "linear-gradient(180deg, #2d4668 0 3px, transparent 3px calc(100% - 3px), #2d4668 calc(100% - 3px) 100%)",
        "linear-gradient(135deg, rgba(255,255,255,0.4), transparent 45%)",
      ].join(","),
      boxShadow: "inset 0 -3px 0 rgba(45, 70, 104, 0.4)",
    };
  }

  if (fixture === "door") {
    return {
      backgroundColor: "#7f5334",
      backgroundImage: [
        "linear-gradient(90deg, #50331f 0 2px, transparent 2px calc(100% - 2px), #50331f calc(100% - 2px) 100%)",
        "linear-gradient(180deg, #c99761 0 3px, transparent 3px 100%)",
        "radial-gradient(circle at 78% 58%, #e8cf8c 0 2px, transparent 2px 100%)",
      ].join(","),
      boxShadow: "inset 0 -3px 0 rgba(48, 27, 16, 0.4)",
    };
  }

  if (fixture === "desk-left" || fixture === "desk-mid" || fixture === "desk-right") {
    const edge =
      fixture === "desk-left"
        ? "linear-gradient(90deg, rgba(59,39,23,0.95) 0 3px, transparent 3px 100%)"
        : fixture === "desk-right"
          ? "linear-gradient(90deg, transparent 0 calc(100% - 3px), rgba(59,39,23,0.95) calc(100% - 3px) 100%)"
          : "linear-gradient(90deg, transparent, transparent)";

    return {
      backgroundImage: [
        "linear-gradient(180deg, transparent 0 24%, rgba(38, 48, 62, 0.98) 24% 46%, transparent 46% 100%)",
        "linear-gradient(180deg, transparent 0 48%, #b68455 48% 70%, #6c492d 70% 86%, transparent 86% 100%)",
        "linear-gradient(90deg, transparent 0 18%, rgba(38, 27, 17, 0.9) 18% 22%, transparent 22% 78%, rgba(38, 27, 17, 0.9) 78% 82%, transparent 82% 100%)",
        edge,
      ].join(","),
      backgroundRepeat: "no-repeat",
      boxShadow: "inset 0 -2px 0 rgba(0,0,0,0.2)",
    };
  }

  if (fixture === "chair") {
    return {
      backgroundImage: [
        "linear-gradient(180deg, transparent 0 8%, #3b4250 8% 36%, transparent 36% 100%)",
        "linear-gradient(180deg, transparent 0 44%, #65718d 44% 66%, transparent 66% 100%)",
        "linear-gradient(90deg, transparent 0 46%, #2b2f3a 46% 54%, transparent 54% 100%)",
        "linear-gradient(90deg, transparent 0 22%, #2b2f3a 22% 26%, transparent 26% 74%, #2b2f3a 74% 78%, transparent 78% 100%)",
      ].join(","),
      backgroundRepeat: "no-repeat",
    };
  }

  if (fixture === "shelf") {
    return {
      backgroundColor: "#7d5633",
      backgroundImage: [
        "linear-gradient(180deg, rgba(52,34,21,0.9) 0 2px, transparent 2px 100%)",
        "linear-gradient(180deg, transparent 0 32%, rgba(52,34,21,0.9) 32% 36%, transparent 36% 68%, rgba(52,34,21,0.9) 68% 72%, transparent 72% 100%)",
        "repeating-linear-gradient(90deg, transparent 0 3px, #c45f6a 3px 5px, #d1bb74 5px 7px, #5f95d1 7px 9px, transparent 9px 12px)",
      ].join(","),
      backgroundRepeat: "no-repeat",
    };
  }

  if (fixture === "plant") {
    return {
      backgroundImage: [
        "radial-gradient(circle at 30% 40%, #7cd768 0 16%, transparent 16% 100%)",
        "radial-gradient(circle at 65% 35%, #65bb59 0 18%, transparent 18% 100%)",
        "radial-gradient(circle at 50% 18%, #93e37f 0 16%, transparent 16% 100%)",
        "linear-gradient(180deg, transparent 0 60%, #b57a43 60% 82%, #54351d 82% 100%)",
      ].join(","),
      backgroundRepeat: "no-repeat",
    };
  }

  if (fixture === "frame") {
    return {
      backgroundImage: [
        "linear-gradient(90deg, #3a2617 0 3px, transparent 3px calc(100% - 3px), #3a2617 calc(100% - 3px) 100%)",
        "linear-gradient(180deg, #3a2617 0 3px, transparent 3px calc(100% - 3px), #3a2617 calc(100% - 3px) 100%)",
        "linear-gradient(135deg, #96d5ff 0 50%, #f7c96b 50% 100%)",
      ].join(","),
      backgroundColor: "#e4d6bf",
      backgroundRepeat: "no-repeat",
    };
  }

  if (fixture === "sofa-left" || fixture === "sofa-right") {
    return {
      backgroundImage: [
        "linear-gradient(180deg, transparent 0 18%, #4f6a8f 18% 46%, #364a68 46% 100%)",
        fixture === "sofa-left"
          ? "linear-gradient(90deg, #27354d 0 18%, transparent 18% 100%)"
          : "linear-gradient(90deg, transparent 0 82%, #27354d 82% 100%)",
        "linear-gradient(180deg, transparent 0 76%, #253246 76% 100%)",
      ].join(","),
      backgroundRepeat: "no-repeat",
      boxShadow: "inset 0 -2px 0 rgba(0,0,0,0.18)",
    };
  }

  if (fixture === "cabinet") {
    return {
      backgroundColor: "#b7865b",
      backgroundImage: [
        "linear-gradient(180deg, rgba(255,255,255,0.14) 0 18%, transparent 18% 100%)",
        "linear-gradient(180deg, transparent 0 50%, rgba(88,56,33,0.6) 50% 54%, transparent 54% 100%)",
        "radial-gradient(circle at 76% 28%, #f0deab 0 1.5px, transparent 1.5px 100%)",
        "radial-gradient(circle at 76% 72%, #f0deab 0 1.5px, transparent 1.5px 100%)",
      ].join(","),
      backgroundRepeat: "no-repeat",
    };
  }

  if (fixture === "server") {
    return {
      backgroundColor: "#283042",
      backgroundImage: [
        "repeating-linear-gradient(180deg, rgba(255,255,255,0.08) 0 2px, transparent 2px 5px)",
        "radial-gradient(circle at 28% 30%, #ff8b76 0 1.5px, transparent 1.5px 100%)",
        "radial-gradient(circle at 28% 50%, #8ef07c 0 1.5px, transparent 1.5px 100%)",
        "radial-gradient(circle at 28% 70%, #82c7ff 0 1.5px, transparent 1.5px 100%)",
      ].join(","),
      boxShadow: "inset 0 0 0 2px rgba(16,22,32,0.75)",
    };
  }

  if (fixture === "whiteboard") {
    return {
      backgroundColor: "#f1f4f7",
      backgroundImage: [
        "linear-gradient(90deg, #7a5e45 0 2px, transparent 2px calc(100% - 2px), #7a5e45 calc(100% - 2px) 100%)",
        "linear-gradient(180deg, #7a5e45 0 2px, transparent 2px calc(100% - 2px), #7a5e45 calc(100% - 2px) 100%)",
        "linear-gradient(180deg, transparent 0 30%, rgba(108, 164, 215, 0.45) 30% 34%, transparent 34% 54%, rgba(103, 195, 153, 0.45) 54% 58%, transparent 58% 100%)",
      ].join(","),
    };
  }

  if (fixture === "coffee") {
    return {
      backgroundImage: [
        "linear-gradient(180deg, transparent 0 8%, #cad4df 8% 72%, #697382 72% 100%)",
        "radial-gradient(circle at 50% 30%, #2f3949 0 3px, transparent 3px 100%)",
        "linear-gradient(90deg, transparent 0 65%, #7bb7ff 65% 78%, transparent 78% 100%)",
      ].join(","),
      backgroundRepeat: "no-repeat",
    };
  }

  if (fixture === "table") {
    return {
      backgroundImage: [
        "radial-gradient(circle at 50% 44%, #c49362 0 30%, transparent 30% 100%)",
        "linear-gradient(90deg, transparent 0 47%, #5b3b22 47% 53%, transparent 53% 100%)",
        "linear-gradient(90deg, transparent 0 28%, #5b3b22 28% 32%, transparent 32% 68%, #5b3b22 68% 72%, transparent 72% 100%)",
      ].join(","),
      backgroundRepeat: "no-repeat",
    };
  }

  return {
    backgroundImage: [
      "radial-gradient(circle at 50% 20%, #ffe08f 0 16%, transparent 16% 100%)",
      "linear-gradient(90deg, transparent 0 47%, #5d606a 47% 53%, transparent 53% 100%)",
      "linear-gradient(180deg, transparent 0 62%, #3e4653 62% 100%)",
    ].join(","),
    backgroundRepeat: "no-repeat",
  };
}

function getStateLabel(state: CharacterState) {
  return state.charAt(0).toUpperCase() + state.slice(1);
}

function resolveAgentAnchor(
  characterState: CharacterState,
  lastTool: string | null,
  layoutCols: number,
  layoutRows: number
) {
  const tool = (lastTool || "").toLowerCase();

  if (characterState === "reading" || tool.includes("read") || tool.includes("search")) {
    return { col: 5, row: 5 };
  }
  if (characterState === "typing" || tool.includes("write") || tool.includes("edit")) {
    return {
      col: Math.max(7, Math.floor(layoutCols * 0.4)),
      row: Math.max(10, Math.floor(layoutRows * 0.56)),
    };
  }
  if (characterState === "running" || tool.includes("shell") || tool.includes("exec")) {
    return { col: Math.max(4, layoutCols - 6), row: Math.max(4, layoutRows - 6) };
  }
  if (characterState === "waiting") {
    return { col: 5, row: Math.max(4, layoutRows - 6) };
  }
  return {
    col: Math.max(4, Math.floor(layoutCols / 2)),
    row: Math.max(4, Math.floor(layoutRows / 2)),
  };
}

function resolveSubagentAnchor(
  subagent: OfficeSubagent,
  index: number,
  layoutCols: number,
  layoutRows: number
) {
  const baseCol = subagent.status === "running" ? Math.max(6, layoutCols - 8) : 6;
  const baseRow = subagent.status === "running" ? 5 : Math.max(5, layoutRows - 7);
  return {
    col: Math.max(2, baseCol - (index % 3) * 3),
    row: Math.max(2, baseRow + Math.floor(index / 3) * 3),
  };
}

export function OfficeGrid({
  characterState,
  lastTool,
  subagents = [],
  layout: layoutProp,
  cols = DEFAULT_COLS,
  rows = DEFAULT_ROWS,
  tileSize = DEFAULT_TILE_SIZE,
  selectedCell,
  interactive = false,
  onTilePointerDown,
  onTilePointerEnter,
  onTileClick,
}: OfficeGridProps) {
  const layout = useMemo(
    () => layoutProp ?? buildOfficeLayout(cols, rows),
    [cols, layoutProp, rows]
  );
  const layoutCols = layout.cells[0]?.length ?? cols;
  const layoutRows = layout.cells.length || rows;
  const width = layoutCols * tileSize;
  const height = layoutRows * tileSize;
  const agentAnchor = resolveAgentAnchor(
    characterState,
    lastTool,
    layoutCols,
    layoutRows
  );

  return (
    <div className="office-grid-frame">
      <div
        className="office-grid"
        style={{
          width,
          height,
          gridTemplateColumns: `repeat(${layoutCols}, ${tileSize}px)`,
          gridTemplateRows: `repeat(${layoutRows}, ${tileSize}px)`,
        }}
      >
        {layout.cells.flatMap((row, rowIndex) =>
          row.map((cell, colIndex) => {
            const neighbors = {
              north: isStructuralFixture(layout.cells[rowIndex - 1]?.[colIndex]?.fixture),
              south: isStructuralFixture(layout.cells[rowIndex + 1]?.[colIndex]?.fixture),
              east: isStructuralFixture(layout.cells[rowIndex]?.[colIndex + 1]?.fixture),
              west: isStructuralFixture(layout.cells[rowIndex]?.[colIndex - 1]?.fixture),
            };

            return (
              <div
                key={`${rowIndex}-${colIndex}`}
                className={`office-tile${selectedCell?.row === rowIndex && selectedCell?.col === colIndex ? " office-tile--selected" : ""}${interactive ? " office-tile--interactive" : ""}`}
                style={{
                  width: tileSize,
                  height: tileSize,
                  ...getFloorStyle(cell.floor, rowIndex, colIndex),
                }}
                onPointerDown={() => onTilePointerDown?.(rowIndex, colIndex)}
                onPointerEnter={() => onTilePointerEnter?.(rowIndex, colIndex)}
                onClick={() => onTileClick?.(rowIndex, colIndex)}
              >
                {cell.fixture ? (
                  <div
                    className="office-fixture"
                    style={getFixtureStyle(cell.fixture, neighbors)}
                  />
                ) : null}
              </div>
            );
          })
        )}

        <div
          className={`agent-layer agent-layer--${characterState}`}
          style={{
            left: agentAnchor.col * tileSize - tileSize * 0.2,
            top: agentAnchor.row * tileSize - tileSize * 0.9,
          }}
          title={lastTool ? `${getStateLabel(characterState)}: ${lastTool}` : getStateLabel(characterState)}
        >
          <BrainBaby state={characterState} pixelSize={Math.max(1.5, tileSize / 12)} />
        </div>

        {subagents.map((subagent, index) => {
          const anchor = resolveSubagentAnchor(subagent, index, layoutCols, layoutRows);
          return (
            <div
              key={subagent.id}
              className={`subagent-layer subagent-layer--${subagent.status}`}
              style={{
                left: anchor.col * tileSize - tileSize * 0.15,
                top: anchor.row * tileSize - tileSize * 0.85,
              }}
              title={subagent.label}
            >
              <span className="subagent-badge">{subagent.label}</span>
              <BrainBaby state={subagent.status === "running" ? "running" : "idle"} pixelSize={Math.max(1.25, tileSize / 14)} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function StatusLabel({
  characterState,
  lastTool,
  connectionStatus,
}: Pick<OfficeGridProps, "characterState" | "lastTool"> & {
  connectionStatus: string;
}) {
  return (
    <div className="status-label">
      <span>{`State: ${getStateLabel(characterState)}`}</span>
      <span>{`Connection: ${connectionStatus}`}</span>
      <span>{lastTool ? `Tool: ${lastTool}` : "Tool: standby"}</span>
    </div>
  );
}
