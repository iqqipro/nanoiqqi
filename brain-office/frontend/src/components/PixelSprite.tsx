import type { CSSProperties } from "react";

export type PixelPalette = Record<string, string>;

interface PixelSpriteProps {
  rows: string[];
  palette: PixelPalette;
  pixelSize: number;
  className?: string;
  style?: CSSProperties;
  title?: string;
}

export function PixelSprite({
  rows,
  palette,
  pixelSize,
  className,
  style,
  title,
}: PixelSpriteProps) {
  const width = rows.reduce((max, row) => Math.max(max, row.length), 0);

  return (
    <div
      className={className}
      style={{
        display: "inline-grid",
        gridTemplateColumns: `repeat(${width}, ${pixelSize}px)`,
        gridTemplateRows: `repeat(${rows.length}, ${pixelSize}px)`,
        lineHeight: 0,
        imageRendering: "pixelated",
        ...style,
      }}
      title={title}
    >
      {rows.flatMap((row, y) =>
        Array.from({ length: width }, (_, x) => {
          const key = row[x] ?? ".";
          const backgroundColor = palette[key] ?? "transparent";

          return (
            <div
              key={`${y}-${x}`}
              style={{
                width: pixelSize,
                height: pixelSize,
                minWidth: pixelSize,
                minHeight: pixelSize,
                backgroundColor,
                opacity: backgroundColor === "transparent" ? 0 : 1,
              }}
            />
          );
        })
      )}
    </div>
  );
}
