export type FloorKind = "wood" | "carpet" | "tile" | "concrete";

export type FixtureKind =
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

export interface Cell {
  floor: FloorKind;
  fixture?: FixtureKind;
}

export interface OfficeLayout {
  cells: Cell[][];
  agent: {
    col: number;
    row: number;
  };
}

export const DEFAULT_COLS = 32;
export const DEFAULT_ROWS = 24;
export const DEFAULT_TILE_SIZE = 24;

export const FLOOR_OPTIONS: Array<{
  value: FloorKind;
  label: string;
  swatch: string;
}> = [
  { value: "wood", label: "Wood", swatch: "#8b603d" },
  { value: "carpet", label: "Carpet", swatch: "#48516b" },
  { value: "tile", label: "Tile", swatch: "#aeb7c4" },
  { value: "concrete", label: "Concrete", swatch: "#5f6572" },
];

export const FIXTURE_OPTIONS: Array<{
  value: FixtureKind;
  label: string;
  swatch: string;
}> = [
  { value: "wall", label: "Wall", swatch: "#d4be9a" },
  { value: "window", label: "Window", swatch: "#8cc6ff" },
  { value: "door", label: "Door", swatch: "#7f5334" },
  { value: "desk-left", label: "Desk L", swatch: "#b68455" },
  { value: "desk-mid", label: "Desk M", swatch: "#b68455" },
  { value: "desk-right", label: "Desk R", swatch: "#b68455" },
  { value: "chair", label: "Chair", swatch: "#65718d" },
  { value: "shelf", label: "Shelf", swatch: "#7d5633" },
  { value: "plant", label: "Plant", swatch: "#65bb59" },
  { value: "frame", label: "Frame", swatch: "#f7c96b" },
  { value: "sofa-left", label: "Sofa L", swatch: "#4f6a8f" },
  { value: "sofa-right", label: "Sofa R", swatch: "#4f6a8f" },
  { value: "cabinet", label: "Cabinet", swatch: "#b7865b" },
  { value: "server", label: "Server", swatch: "#283042" },
  { value: "whiteboard", label: "Whiteboard", swatch: "#f1f4f7" },
  { value: "coffee", label: "Coffee", swatch: "#cad4df" },
  { value: "table", label: "Table", swatch: "#c49362" },
  { value: "lamp", label: "Lamp", swatch: "#ffe08f" },
];

const FLOOR_VALUES = new Set<FloorKind>(FLOOR_OPTIONS.map((entry) => entry.value));
const FIXTURE_VALUES = new Set<FixtureKind>(FIXTURE_OPTIONS.map((entry) => entry.value));

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

export function cloneLayout(layout: OfficeLayout): OfficeLayout {
  return {
    cells: layout.cells.map((row) => row.map((cell) => ({ ...cell }))),
    agent: { ...layout.agent },
  };
}

export function getLayoutCols(layout: OfficeLayout) {
  return layout.cells[0]?.length ?? 0;
}

export function getLayoutRows(layout: OfficeLayout) {
  return layout.cells.length;
}

export function buildOfficeLayout(cols: number, rows: number): OfficeLayout {
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
  const topOfficeWidth = clamp(Math.floor(cols * 0.18), 6, 8);
  const topOfficeHeight = clamp(Math.floor(rows * 0.18), 5, 6);
  const topOfficeX = clamp(Math.floor(cols / 2) - topOfficeWidth - 1, 10, cols - 20);
  const topOfficeY = 2;

  fillFloorRect(cells, topOfficeX + 1, topOfficeY + 1, topOfficeWidth - 2, topOfficeHeight - 2, "carpet");
  paintRoomWalls(cells, topOfficeX, topOfficeY, topOfficeWidth, topOfficeHeight, {
    x: topOfficeX + Math.floor(topOfficeWidth / 2),
    y: topOfficeY + topOfficeHeight - 1,
  });
  placeDeskRow(cells, topOfficeX + 2, topOfficeY + 2, Math.min(3, topOfficeWidth - 3));
  setFixture(cells, topOfficeX + 2, topOfficeY + 3, "chair");
  setFixture(cells, topOfficeX + topOfficeWidth - 2, topOfficeY + 2, "plant");
  setFixture(cells, topOfficeX + topOfficeWidth - 3, topOfficeY + 1, "frame");

  const topOffice2X = topOfficeX + topOfficeWidth + 2;
  fillFloorRect(cells, topOffice2X + 1, topOfficeY + 1, topOfficeWidth - 2, topOfficeHeight - 2, "tile");
  paintRoomWalls(cells, topOffice2X, topOfficeY, topOfficeWidth, topOfficeHeight, {
    x: topOffice2X + Math.floor(topOfficeWidth / 2),
    y: topOfficeY + topOfficeHeight - 1,
  });
  placeDeskRow(cells, topOffice2X + 2, topOfficeY + 2, Math.min(3, topOfficeWidth - 3));
  setFixture(cells, topOffice2X + 2, topOfficeY + 3, "chair");
  setFixture(cells, topOffice2X + topOfficeWidth - 2, topOfficeY + 2, "cabinet");
  setFixture(cells, topOffice2X + 1, topOfficeY + 1, "whiteboard");

  placeDeskRow(cells, leftBankX, workspaceY, bankWidth);
  placeDeskRow(cells, rightBankX, workspaceY, bankWidth);
  placeDeskRow(cells, leftBankX, workspaceY + 4, bankWidth);
  placeDeskRow(cells, rightBankX, workspaceY + 4, bankWidth);
  placeDeskRow(cells, leftBankX, workspaceY + 8, bankWidth);
  placeDeskRow(cells, rightBankX, workspaceY + 8, bankWidth);

  for (let index = 0; index < bankWidth; index += 1) {
    setFixture(cells, leftBankX + index, workspaceY + 1, "chair");
    setFixture(cells, rightBankX + index, workspaceY + 1, "chair");
    setFixture(cells, leftBankX + index, workspaceY + 5, "chair");
    setFixture(cells, rightBankX + index, workspaceY + 5, "chair");
    if (workspaceY + 9 < rows - 1) {
      setFixture(cells, leftBankX + index, workspaceY + 9, "chair");
      setFixture(cells, rightBankX + index, workspaceY + 9, "chair");
    }
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

export function serializeOfficeLayout(layout: OfficeLayout) {
  return JSON.stringify(layout, null, 2);
}

export function parseOfficeLayout(jsonText: string): OfficeLayout {
  const parsed = JSON.parse(jsonText) as unknown;

  if (
    !parsed ||
    typeof parsed !== "object" ||
    !("cells" in parsed) ||
    !("agent" in parsed)
  ) {
    throw new Error("JSON must include cells and agent.");
  }

  const rawLayout = parsed as {
    cells?: unknown;
    agent?: unknown;
  };

  if (!Array.isArray(rawLayout.cells) || rawLayout.cells.length === 0) {
    throw new Error("cells must be a non-empty 2D array.");
  }

  const width = Array.isArray(rawLayout.cells[0]) ? rawLayout.cells[0].length : 0;
  if (width === 0) {
    throw new Error("cells rows must have at least one column.");
  }

  const cells = rawLayout.cells.map((row, rowIndex) => {
    if (!Array.isArray(row) || row.length !== width) {
      throw new Error(`Row ${rowIndex} has an invalid width.`);
    }

    return row.map((cell, colIndex) => {
      if (!cell || typeof cell !== "object" || !("floor" in cell)) {
        throw new Error(`Cell ${rowIndex},${colIndex} must define floor.`);
      }

      const candidate = cell as { floor?: unknown; fixture?: unknown };
      if (!FLOOR_VALUES.has(candidate.floor as FloorKind)) {
        throw new Error(`Cell ${rowIndex},${colIndex} has invalid floor.`);
      }
      if (
        candidate.fixture !== undefined &&
        !FIXTURE_VALUES.has(candidate.fixture as FixtureKind)
      ) {
        throw new Error(`Cell ${rowIndex},${colIndex} has invalid fixture.`);
      }

      return {
        floor: candidate.floor as FloorKind,
        fixture: candidate.fixture as FixtureKind | undefined,
      };
    });
  });

  if (!rawLayout.agent || typeof rawLayout.agent !== "object") {
    throw new Error("agent must be an object.");
  }

  const rawAgent = rawLayout.agent as { col?: unknown; row?: unknown };
  if (typeof rawAgent.col !== "number" || typeof rawAgent.row !== "number") {
    throw new Error("agent row and col must be numbers.");
  }

  return {
    cells,
    agent: {
      col: clamp(Math.round(rawAgent.col), 0, width - 1),
      row: clamp(Math.round(rawAgent.row), 0, cells.length - 1),
    },
  };
}
