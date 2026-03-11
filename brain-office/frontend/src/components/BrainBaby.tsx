import { useMemo } from "react";

import type { CharacterState } from "../types";
import { PixelSprite, type PixelPalette } from "./PixelSprite";

const W = 22;
const H = 22;

const PALETTE: PixelPalette = {
  ".": "transparent",
  K: "rgb(12, 12, 12)",
  P: "rgb(255, 148, 172)",
  M: "rgb(232, 105, 135)",
  D: "rgb(198, 68, 98)",
  L: "rgb(255, 210, 228)",
  S: "rgb(235, 235, 235)",
  R: "rgb(255, 182, 193)",
  B: "rgb(72, 148, 255)",
  b: "rgb(35, 88, 200)",
  G: "rgb(168, 210, 255)",
  Y: "rgb(245, 220, 88)",
  y: "rgb(197, 154, 33)",
  g: "rgb(138, 201, 106)",
  n: "rgb(241, 233, 203)",
  C: "rgb(94, 168, 174)",
  c: "rgb(52, 105, 117)",
};

const STATE_GLOW: Record<CharacterState, string> = {
  idle: "drop-shadow(0 2px 0 rgba(12, 12, 12, 0.3))",
  reading:
    "drop-shadow(0 2px 0 rgba(12, 12, 12, 0.3)) drop-shadow(0 0 8px rgba(138, 201, 106, 0.45))",
  typing:
    "drop-shadow(0 2px 0 rgba(12, 12, 12, 0.3)) drop-shadow(0 0 8px rgba(245, 220, 88, 0.55))",
  running:
    "drop-shadow(0 2px 0 rgba(12, 12, 12, 0.3)) drop-shadow(2px 0 0 rgba(198, 68, 98, 0.25))",
  waiting:
    "drop-shadow(0 2px 0 rgba(12, 12, 12, 0.3)) drop-shadow(0 0 8px rgba(168, 210, 255, 0.55))",
};

type Grid = string[][];

function seededRandom(seed: number) {
  return function next() {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };
}

function buildGrid(state: CharacterState): string[] {
  const grid: Grid = Array.from({ length: H }, () => Array(W).fill("."));

  const px = (x: number, y: number, c: string) => {
    if (x >= 0 && x < W && y >= 0 && y < H) {
      grid[y][x] = c;
    }
  };

  const rect = (x: number, y: number, w: number, h: number, c: string) => {
    for (let j = 0; j < h; j += 1) {
      for (let i = 0; i < w; i += 1) {
        px(x + i, y + j, c);
      }
    }
  };

  const clear = (x: number, y: number, w: number, h: number) => {
    rect(x, y, w, h, ".");
  };

  const disk = (cx: number, cy: number, rx: number, ry: number, c: string) => {
    for (let j = -ry - 1; j <= ry + 1; j += 1) {
      for (let i = -rx - 1; i <= rx + 1; i += 1) {
        if ((i / rx) ** 2 + (j / ry) ** 2 <= 1.0) {
          px(cx + i, cy + j, c);
        }
      }
    }
  };

  const ring = (
    cx: number,
    cy: number,
    rx: number,
    ry: number,
    c: string,
    t = 1
  ) => {
    for (let j = -ry - t - 1; j <= ry + t + 1; j += 1) {
      for (let i = -rx - t - 1; i <= rx + t + 1; i += 1) {
        const outer = (i / (rx + t)) ** 2 + (j / (ry + t)) ** 2;
        const inner = (i / rx) ** 2 + (j / ry) ** 2;
        if (outer <= 1.0 && inner > 1.0) {
          px(cx + i, cy + j, c);
        }
      }
    }
  };

  const BCX = 11;
  const BCY = 6;
  const BRX = 7;
  const BRY = 5;

  disk(BCX, BCY, BRX, BRY, "P");

  const rnd = seededRandom(7);
  const choices = ["M", "D", "L", "P"];
  for (let n = 0; n < 50; n += 1) {
    const tx = Math.floor(BCX - BRX + 1 + rnd() * (2 * BRX - 1));
    const ty = Math.floor(BCY - BRY + 1 + rnd() * (2 * BRY - 1));
    if (((tx - BCX) / BRX) ** 2 + ((ty - BCY) / BRY) ** 2 <= 0.92) {
      const value = rnd();
      const thresholds = [3 / 11, 5 / 11, 7 / 11, 1];
      let shade = "P";
      for (let i = 0; i < thresholds.length; i += 1) {
        if (value < thresholds[i]) {
          shade = choices[i];
          break;
        }
      }
      rect(tx, ty, Math.floor(rnd() * 2) + 1, Math.floor(rnd() * 2) + 1, shade);
    }
  }

  ring(BCX, BCY, BRX, BRY, "K");
  for (let y = BCY - BRY + 1; y < BCY - 1; y += 1) {
    px(BCX, y, "K");
    px(BCX + 1, y, "D");
  }

  rect(7, 7, 3, 3, "K");
  rect(12, 7, 3, 3, "K");
  px(8, 8, "L");
  px(13, 8, "L");
  px(9, 9, "R");
  px(14, 9, "R");

  const pacifierX = 11;
  const pacifierY = 11;
  disk(pacifierX, pacifierY, 3, 2, "B");
  ring(pacifierX, pacifierY, 3, 2, "b");
  disk(pacifierX, pacifierY, 1, 1, "b");
  px(pacifierX - 1, pacifierY - 1, "G");
  px(pacifierX - 1, pacifierY, "G");
  px(pacifierX - 1, pacifierY + 1, "S");
  px(pacifierX, pacifierY + 1, "S");
  px(pacifierX + 1, pacifierY + 1, "S");
  ring(pacifierX, pacifierY, 3, 2, "K");

  rect(3, 9, 1, 2, "K");
  rect(4, 9, 1, 2, "P");
  rect(5, 9, 1, 2, "K");
  rect(2, 10, 1, 2, "K");
  rect(3, 10, 2, 2, "P");
  rect(5, 10, 1, 2, "K");
  rect(3, 12, 2, 1, "K");
  rect(17, 9, 1, 2, "K");
  rect(18, 9, 1, 2, "P");
  rect(19, 9, 1, 2, "K");
  rect(17, 10, 1, 2, "K");
  rect(18, 10, 2, 2, "P");
  rect(20, 10, 1, 2, "K");
  rect(18, 12, 2, 1, "K");

  rect(8, 13, 1, 2, "K");
  rect(9, 13, 1, 2, "P");
  rect(10, 13, 1, 2, "K");
  rect(12, 13, 1, 2, "K");
  rect(13, 13, 1, 2, "P");
  rect(14, 13, 1, 2, "K");

  rect(6, 15, 1, 2, "K");
  rect(7, 15, 3, 2, "P");
  rect(10, 15, 1, 2, "K");
  rect(6, 17, 4, 1, "K");
  [7, 8, 9].forEach((x) => px(x, 14, "P"));
  px(6, 14, "K");
  px(10, 14, "K");
  rect(12, 15, 1, 2, "K");
  rect(13, 15, 3, 2, "P");
  rect(16, 15, 1, 2, "K");
  rect(12, 17, 4, 1, "K");
  [13, 14, 15].forEach((x) => px(x, 14, "P"));
  px(12, 14, "K");
  px(16, 14, "K");

  if (state === "reading") {
    rect(7, 13, 8, 4, "g");
    rect(8, 13, 3, 3, "n");
    rect(11, 13, 3, 3, "n");
    px(11, 13, "K");
    px(11, 14, "K");
    px(11, 15, "K");
    rect(4, 12, 2, 1, "P");
    rect(16, 12, 2, 1, "P");
    rect(3, 13, 2, 1, "K");
    rect(17, 13, 2, 1, "K");
  }

  if (state === "typing") {
    rect(6, 13, 10, 2, "K");
    rect(7, 13, 8, 1, "Y");
    px(8, 14, "y");
    px(10, 14, "y");
    px(12, 14, "y");
    px(14, 14, "y");
    clear(3, 9, 3, 4);
    clear(17, 9, 4, 4);
    rect(4, 10, 1, 3, "K");
    rect(5, 10, 1, 3, "P");
    rect(6, 10, 3, 1, "K");
    rect(15, 10, 3, 1, "K");
    rect(17, 10, 1, 3, "P");
    rect(18, 10, 1, 3, "K");
  }

  if (state === "running") {
    clear(6, 13, 11, 5);
    clear(2, 9, 4, 4);
    clear(17, 9, 4, 4);

    rect(5, 10, 1, 3, "K");
    rect(6, 10, 1, 3, "P");
    rect(7, 9, 1, 2, "K");
    rect(16, 9, 1, 2, "K");
    rect(17, 10, 1, 3, "P");
    rect(18, 10, 1, 3, "K");
    rect(7, 13, 1, 2, "K");
    rect(8, 13, 1, 2, "P");
    rect(9, 13, 1, 2, "K");
    rect(12, 14, 1, 2, "K");
    rect(13, 14, 1, 2, "P");
    rect(14, 14, 1, 2, "K");
    rect(5, 15, 1, 2, "K");
    rect(6, 15, 3, 2, "P");
    rect(9, 15, 1, 2, "K");
    rect(13, 16, 1, 2, "K");
    rect(14, 16, 3, 1, "P");
    rect(17, 16, 1, 1, "K");
    rect(2, 8, 1, 1, "M");
    rect(1, 9, 1, 1, "D");
    rect(0, 10, 1, 1, "L");
  }

  if (state === "waiting") {
    rect(8, 0, 7, 3, "S");
    rect(9, 1, 1, 1, "K");
    rect(11, 1, 1, 1, "K");
    rect(13, 1, 1, 1, "K");
    px(10, 2, "G");
    px(12, 2, "G");
    px(11, 3, "S");
  }

  let rows = grid.map((row) => row.join(""));
  while (rows.length > 0 && rows[rows.length - 1].split("").every((cell) => cell === ".")) {
    rows = rows.slice(0, -1);
  }
  return rows;
}

interface BrainBabyProps {
  state: CharacterState;
  pixelSize?: number;
  className?: string;
  title?: string;
}

export function BrainBaby({
  state,
  pixelSize = 2,
  className,
  title,
}: BrainBabyProps) {
  const rows = useMemo(() => buildGrid(state), [state]);

  return (
    <div
      className={className}
      style={{
        display: "inline-block",
        filter: STATE_GLOW[state],
        transformOrigin: "bottom center",
      }}
    >
      <PixelSprite rows={rows} palette={PALETTE} pixelSize={pixelSize} title={title} />
    </div>
  );
}
