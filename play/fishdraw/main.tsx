import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { fish, generate_params } from "./fishdraw";

// --- helpers ---
function bboxFromPolylines(polylines) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

  for (const line of polylines) {
    for (const p of line) {
      // fishdraw polyline points are typically [x,y] (or {x,y} in some libs);
      // support both defensively.
      const x = Array.isArray(p) ? p[0] : p.x;
      const y = Array.isArray(p) ? p[1] : p.y;
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      minX = Math.min(minX, x); minY = Math.min(minY, y);
      maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
    }
  }

  if (!Number.isFinite(minX)) return { minX: 0, minY: 0, maxX: 1, maxY: 1 };
  return { minX, minY, maxX, maxY };
}

function polylineToPointsAttr(line) {
  return line
    .map((p) => {
      const x = Array.isArray(p) ? p[0] : p.x;
      const y = Array.isArray(p) ? p[1] : p.y;
      return `${x},${y}`;
    })
    .join(" ");
}

function downloadSvg(svgText, filename = "fish.svg") {
  const blob = new Blob([svgText], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// --- app ---
export default function App() {
  const [seed, setSeed] = useState("cara");
  const [nonce, setNonce] = useState(0); // force regen even if seed unchanged

  const { polylines, viewBox } = useMemo(() => {
    // fishdraw’s seed is a *string* per README; generate_params() takes optional args in its own schema.
    // If your local fishdraw.js wants seed differently, adapt here.
    const params = generate_params();
    const polylines = fish(params);

    const { minX, minY, maxX, maxY } = bboxFromPolylines(polylines);
    const pad = 10;
    const vb = `${minX - pad} ${minY - pad} ${maxX - minX + 2 * pad} ${maxY - minY + 2 * pad}`;
    return { polylines, viewBox: vb };
  }, [nonce]);

  const svgText = useMemo(() => {
    // serialize for download (kept simple: black strokes, no fill)
    const paths = polylines
      .map(
        (line) =>
          `<polyline points="${polylineToPointsAttr(line)}" fill="none" stroke="black" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" />`
      )
      .join("\n");

    return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}">
${paths}
</svg>`;
  }, [polylines, viewBox]);

  return (
    <div style={{ maxWidth: 900, margin: "40px auto", padding: 16, fontFamily: "ui-sans-serif, system-ui" }}>
      <h1 style={{ margin: 0 }}>Fishdraw Viewer</h1>
      <p style={{ marginTop: 8, opacity: 0.75 }}>
        Procedurally generated fish! Enter a name for your fish and click "generate."
      </p>
      <p style={{ marginTop: 8, opacity: 0.75 }}>
        <small>
          Algorithm originally from <a href="https://github.com/LingDong-/fishdraw" target="_blank" rel="noreferrer">LingDong-/fishdraw</a>. Fixed by Noah Trupin, viewer by Noah + GPT 5.2.
        </small>
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 16, flexWrap: "wrap" }}>
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ minWidth: 40 }}>name</span>
          <input
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            style={{ width: 320, padding: "8px 10px", borderRadius: 8, border: "1px solid #ddd" }}
          />
        </label>

        <button
          onClick={() => setNonce((n) => n + 1)}
          style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #ddd", background: "white", cursor: "pointer" }}
        >
          generate
        </button>

        <button
          onClick={() => downloadSvg(svgText, `${seed || "fish"}.svg`)}
          style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #ddd", background: "white", cursor: "pointer" }}
        >
          download SVG
        </button>
      </div>

      <div style={{ marginTop: 18, border: "1px solid #eee", borderRadius: 12, padding: 12 }}>
        <svg
          viewBox={viewBox}
          style={{ width: "100%", height: 520, display: "block", background: "white" }}
        >
          {polylines.map((line, i) => (
            <polyline
              key={i}
              points={polylineToPointsAttr(line)}
              fill="none"
              stroke="black"
              strokeWidth="1"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}
        </svg>
      </div>

      <details style={{ marginTop: 12 }}>
        <summary>debug</summary>
        <pre style={{ whiteSpace: "pre-wrap" }}>
          polylines: {polylines.length}
          {"\n"}viewBox: {viewBox}
        </pre>
      </details>
    </div>
  );
}

if (typeof document !== "undefined") {
  const el = document.getElementById("root") || (() => {
    const d = document.createElement("div");
    d.id = "root";
    document.body.appendChild(d);
    return d;
  })();
  createRoot(el).render(<App />);
}
