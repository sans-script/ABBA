// A lyric word as bevelled lettering, built from its outline (font units,
// baseline at y = 0). Layers, back to front:
//   glints, glow, bevelled face, crisp edge line.

import { el, seeded, uid } from "./util.js";

// Hue pairing: words alternate warm and cool in reading order. Each face
// gradient runs across the word from a light start toward cyan, so warm
// words still lean cool at their end, as in the reference.
export const PALETTES = [
  {
    name: "warm",
    // Gold, sampled from the reference warm words (#fceec2 / #f4deb3 /
    // #c7bc94, turning olive toward cyan) and pushed more saturated.
    face: [["0", "#fff1c4"], ["0.3", "#f4cd7c"], ["0.55", "#dba64a"], ["0.8", "#b5c58a"], ["1", "#6fd0c8"]],
    edge: "#2a5a60",
    glow: "#ffd9ad",
  },
  {
    name: "cool",
    face: [["0", "#e2fffa"], ["0.35", "#86eee3"], ["0.7", "#38cbe8"], ["1", "#1d9bd3"]],
    edge: "#134f60",
    glow: "#5fe3ff",
  },
];

export function buildWord(defs, parent, outline, index, seed) {
  const palette = PALETTES[index % PALETTES.length];
  const group = el("g", { class: `word word--${palette.name}` }, parent);
  const body = el("g", {}, group);

  const pathId = uid("glyphs");
  el("path", { id: pathId, d: outline.d }, defs);
  const ref = `#${pathId}`;

  const faceId = uid("face");
  const face = el("linearGradient", { id: faceId, x1: "0", y1: "0.15", x2: "1", y2: "0.85" }, defs);
  for (const [offset, color] of palette.face) {
    el("stop", { offset, "stop-color": color }, face);
  }

  const glints = el("g", { class: "glints" }, body);
  const glow = el("use", { href: ref, fill: palette.glow, filter: "url(#word-glow)" }, body);

  el("use", { href: ref, fill: `url(#${faceId})`, filter: "url(#bevel)" }, body);
  // Crisp edge around the silhouette, like cut metal.
  el("use", { href: ref, fill: "none", stroke: palette.edge, "stroke-width": 5, "stroke-opacity": "0.75", "stroke-linejoin": "round" }, body);

  return {
    group,
    body,
    glow,
    advance: outline.advance,
    depth: [0, 0],
    placeGlints(box) {
      // Star-glints catch light behind the upper strokes.
      const random = seeded(seed);
      const count = 2;
      const items = [];
      for (let i = 0; i < count; i++) {
        const x = box.x + box.width * (0.15 + 0.7 * random());
        const y = box.y + box.height * (0.15 + 0.35 * random());
        const size = 320 + random() * 240;
        const g = el("g", { transform: `translate(${x} ${y})`, style: "mix-blend-mode: screen" }, glints);
        const rays = el("g", { filter: "url(#glint-soft)" }, g);
        el("ellipse", { rx: size * 1.2, ry: size * 0.06, fill: "url(#glint-ray)" }, rays);
        el("ellipse", { rx: size * 0.06, ry: size * 0.9, fill: "url(#glint-ray)" }, rays);
        el("circle", { r: size * 0.22, fill: "url(#glint-ray)", opacity: "0.6" }, rays);
        el("circle", { r: size * 0.05, fill: "#ffffff" }, g);
        items.push({ node: g, x, y, phase: random() * Math.PI * 2 });
      }
      return items;
    },
  };
}
