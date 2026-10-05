// Decorative shape library and layouts, in a 1920 x 1080 frame.
// Shapes take the video's vocabulary (holographic shards, gold and foil
// triangles, iridescent spheres, four-point sparkles, expanding rings,
// lightning streaks, prism rays) but
// layouts are our own.

import { clamp, el, lerp, seeded, uid } from "./util.js";

// Four-point sparkle as in the reference: upright, full-bodied, sides
// curving in gently (each side's midpoint sits ~0.3 from the centre).
const SPARKLE = "M0,-1 C0.23,-0.23 0.23,-0.23 1,0 C0.23,0.23 0.23,0.23 0,1 C-0.23,0.23 -0.23,0.23 -1,0 C-0.23,-0.23 -0.23,-0.23 0,-1Z";

const SHAPES = {
  shard(parent, { points, fill = "holo-pink" }) {
    const g = el("g", { filter: "url(#edge-glow)" }, parent);
    el("polygon", { points, fill: `url(#${fill})` }, g);
    el("polygon", { points, fill: "url(#hotspot)", style: "mix-blend-mode: screen" }, g);
    return g;
  },

  foil(parent, { points }) {
    const g = el("g", {}, parent);
    el("polygon", { points, fill: "url(#gold)", filter: "url(#foil)" }, g);
    return g;
  },

  sphere(parent, { cx, cy, r }, defs) {
    const g = el("g", {}, parent);
    el("circle", { cx, cy, r: r * 1.1, fill: "#fff2f8", opacity: "0.35", filter: "url(#big-glow)" }, g);
    const clipId = uid("sphere");
    const clip = el("clipPath", { id: clipId }, defs);
    el("circle", { cx, cy, r }, clip);
    const inner = el("g", { "clip-path": `url(#${clipId})` }, g);
    const flow = el("rect", {
      x: cx - r * 1.6, y: cy - r * 1.6, width: r * 3.2, height: r * 3.2,
      fill: "url(#iridescent)", filter: "url(#swirl)",
    }, inner);
    el("circle", { cx, cy, r, fill: "url(#sphere-shade)" }, inner);
    el("circle", { cx, cy, r, fill: "url(#hotspot)", opacity: "0.6", style: "mix-blend-mode: screen" }, inner);
    return Object.assign(g, { flow, center: [cx, cy] });
  },

  sparkle(parent, { x, y, size }) {
    const g = el("g", { transform: `translate(${x} ${y})` }, parent);
    const inner = el("g", {}, g);
    // Soft light beams behind, angled like light falling from upper left.
    const beams = el("g", { filter: "url(#beam-blur)", style: "mix-blend-mode: screen" }, inner);
    el("ellipse", { rx: size * 2.6, ry: size * 0.22, fill: "#9eeaff", opacity: "0.35", transform: "rotate(-40)" }, beams);
    el("ellipse", { rx: size * 1.8, ry: size * 0.16, fill: "#ffd6ec", opacity: "0.25", transform: "rotate(-62)" }, beams);
    el("path", { d: SPARKLE, fill: "#d8fff8", opacity: "0.55", filter: "url(#big-glow)", transform: `scale(${size * 1.25})` }, inner);
    el("path", { d: SPARKLE, fill: "url(#sparkle-fill)", transform: `scale(${size})` }, inner);
    el("path", { d: SPARKLE, fill: "url(#hotspot)", style: "mix-blend-mode: screen", transform: `scale(${size})` }, inner);
    return Object.assign(g, { inner });
  },

  // Expanding ring, measured frame by frame from the reference (15.0-15.9
  // s): one ring at a time, growing at a steady rate from ~19% to full
  // radius in ~0.9 s while its stroke thins from ~24% of the radius to a
  // hairline, fully opaque, then gone; the next one follows after a pause.
  ring(parent, { cx, cy, radius, life = 0.9, rest = 1.6, stroke = "ring" }) {
    const g = el("g", { filter: "url(#edge-glow)" }, parent);
    const circle = el("circle", { cx, cy, r: 0, fill: "none", stroke: `url(#${stroke})`, opacity: 0 }, g);

    return Object.assign(g, {
      update(time) {
        const local = ((time % (life + rest)) + life + rest) % (life + rest);
        const t = local / life;
        if (t >= 1) {
          circle.setAttribute("opacity", "0");
          return;
        }
        const r = radius * lerp(0.19, 1, t);
        const width = r * lerp(0.24, 0.02, t ** 1.3);
        circle.setAttribute("r", r.toFixed(1));
        circle.setAttribute("stroke-width", width.toFixed(1));
        circle.setAttribute("opacity", clamp(t / 0.04).toFixed(3));
      },
    });
  },

  // Jagged lightning streak from (x1, y1) to (x2, y2): a zigzag centre line
  // widened into a polygon that tapers to a point at both ends; flickers.
  bolt(parent, { x1, y1, x2, y2, width = 34, segments = 7, seed = 1, fill = "holo-blue" }) {
    const random = seeded(seed);
    const dx = x2 - x1;
    const dy = y2 - y1;
    const length = Math.hypot(dx, dy);
    const [nx, ny] = [-dy / length, dx / length];
    const spine = Array.from({ length: segments + 1 }, (_, i) => {
      const t = i / segments;
      const swing = i === 0 || i === segments ? 0 : (i % 2 ? 1 : -1) * length * (0.05 + 0.05 * random());
      return [x1 + dx * t + nx * swing, y1 + dy * t + ny * swing, t];
    });
    const side = (sign) => spine.map(([x, y, t]) => {
      const w = width * Math.sin(Math.PI * t) * 0.5 * sign;
      return `${(x + nx * w).toFixed(1)},${(y + ny * w).toFixed(1)}`;
    });
    const points = [...side(1), ...side(-1).reverse()].join(" ");
    const g = el("g", { filter: "url(#edge-glow)" }, parent);
    el("polygon", { points, fill: `url(#${fill})` }, g);
    el("polygon", { points, fill: "url(#hotspot)", style: "mix-blend-mode: screen" }, g);

    return Object.assign(g, {
      update(time) {
        // Mostly steady with brief flickers, like a discharge.
        const flicker = Math.sin(time * 23) * Math.sin(time * 7.3 + seed) > 0.7 ? 0.55 : 1;
        g.setAttribute("opacity", flicker);
      },
    });
  },

  // Prism rays: rainbow beams fanning out from (cx, cy), slowly swaying.
  rays(parent, { cx, cy, length = 1400, count = 5, angle = 20, spread = 40 }) {
    const g = el("g", { style: "mix-blend-mode: screen", filter: "url(#ray-blur)" }, parent);
    const fan = el("g", {}, g);
    for (let i = 0; i < count; i++) {
      const a = ((angle - spread / 2 + (spread * i) / Math.max(1, count - 1)) * Math.PI) / 180;
      const half = (0.02 + 0.015 * (i % 2)) * length;
      const ex = cx + Math.cos(a) * length;
      const ey = cy + Math.sin(a) * length;
      const [px, py] = [-Math.sin(a) * half, Math.cos(a) * half];
      el("polygon", {
        points: `${cx},${cy} ${ex + px},${ey + py} ${ex - px},${ey - py}`,
        fill: "url(#prism-ray)",
        opacity: (0.35 + 0.25 * (i % 2)).toFixed(2),
      }, fan);
    }

    return Object.assign(g, {
      update(time) {
        fan.setAttribute("transform", `rotate(${(Math.sin(time * 0.35) * 4).toFixed(2)} ${cx} ${cy})`);
      },
    });
  },
};

// depth: how strongly a shape drifts as the scene plays (parallax).
export const LAYOUTS = {
  "constellation-a": [
    { type: "shard", points: "250,150 760,70 560,420", fill: "holo-pink", depth: 0.6 },
    { type: "sphere", cx: 1560, cy: 290, r: 175, depth: 0.4 },
    { type: "shard", points: "40,820 880,930 60,880", fill: "holo-blue", depth: 0.9 },
    { type: "shard", points: "1470,1120 1650,500 1790,1120", fill: "gold", depth: 0.5 },
    { type: "foil", points: "520,1010 720,1000 610,850", depth: 0.7 },
    { type: "ring", cx: 330, cy: 610, radius: 300, depth: 0.8 },
    { type: "ring", cx: 1300, cy: 900, radius: 260, stroke: "ring-pink", rest: 2.3, depth: 0.6 },
    { type: "shard", points: "1180,960 1880,840 1890,880", fill: "holo-blue", depth: 1 },
    { type: "sparkle", x: 1180, y: 160, size: 92, depth: 0.3 },
    { type: "sparkle", x: 180, y: 470, size: 64, depth: 0.5 },
    { type: "sparkle", x: 1820, y: 640, size: 54, depth: 0.4 },
    { type: "sparkle", x: 960, y: 980, size: 40, depth: 0.6 },
  ],

  moonrise: [
    { type: "sphere", cx: 300, cy: 930, r: 270, depth: 0.3 },
    { type: "shard", points: "1300,60 1880,140 1560,380", fill: "holo-pink", depth: 0.6 },
    { type: "foil", points: "140,120 360,90 230,300", depth: 0.7 },
    { type: "shard", points: "1840,520 1900,1080 1660,1080", fill: "holo-blue", depth: 0.8 },
    { type: "ring", cx: 1560, cy: 760, radius: 280, stroke: "ring-pink", depth: 0.5 },
    { type: "sparkle", x: 700, y: 140, size: 70, depth: 0.4 },
    { type: "sparkle", x: 1240, y: 960, size: 56, depth: 0.5 },
    { type: "sparkle", x: 1760, y: 470, size: 40, depth: 0.6 },
  ],

  orbit: [
    { type: "sphere", cx: 1480, cy: 230, r: 150, depth: 0.3 },
    { type: "ring", cx: 1480, cy: 230, radius: 360, rest: 1.2, depth: 0.3 },
    { type: "shard", points: "60,140 640,40 240,360", fill: "holo-blue", depth: 0.7 },
    { type: "shard", points: "120,1100 330,560 470,1100", fill: "gold", depth: 0.6 },
    { type: "shard", points: "1250,1000 1900,860 1880,920", fill: "holo-pink", depth: 0.9 },
    { type: "sparkle", x: 860, y: 120, size: 60, depth: 0.4 },
    { type: "sparkle", x: 600, y: 930, size: 48, depth: 0.5 },
    { type: "sparkle", x: 1800, y: 600, size: 72, depth: 0.4 },
    { type: "sparkle", x: 1080, y: 1000, size: 34, depth: 0.6 },
  ],

  prism: [
    { type: "rays", cx: 120, cy: 120, length: 1900, count: 5, angle: 24, spread: 30, depth: 0.2 },
    { type: "shard", points: "1500,1120 1690,560 1840,1120", fill: "gold", depth: 0.5 },
    { type: "foil", points: "1280,140 1500,110 1380,330", depth: 0.7 },
    { type: "shard", points: "40,760 700,1000 80,1000", fill: "holo-pink", depth: 0.8 },
    { type: "ring", cx: 1700, cy: 300, radius: 240, depth: 0.6 },
    { type: "sparkle", x: 260, y: 540, size: 58, depth: 0.5 },
    { type: "sparkle", x: 980, y: 990, size: 44, depth: 0.6 },
    { type: "sparkle", x: 1100, y: 120, size: 80, depth: 0.3 },
  ],

  storm: [
    { type: "bolt", x1: 1780, y1: -40, x2: 1380, y2: 1120, width: 46, segments: 7, seed: 3, depth: 0.5 },
    { type: "bolt", x1: 180, y1: 1120, x2: 520, y2: 380, width: 28, segments: 5, seed: 8, fill: "gold", depth: 0.7 },
    { type: "sphere", cx: 420, cy: 200, r: 120, depth: 0.4 },
    { type: "ring", cx: 420, cy: 200, radius: 260, stroke: "ring-pink", rest: 1.4, depth: 0.4 },
    { type: "shard", points: "1050,1000 1300,940 1190,1100", fill: "holo-blue", depth: 0.8 },
    { type: "sparkle", x: 1560, y: 520, size: 64, depth: 0.5 },
    { type: "sparkle", x: 860, y: 110, size: 50, depth: 0.4 },
    { type: "sparkle", x: 120, y: 650, size: 40, depth: 0.6 },
  ],
};

export function buildDecor(defs, parent, layoutName) {
  return (LAYOUTS[layoutName] || []).map((spec, i) => {
    const wrap = el("g", {}, parent);
    const node = SHAPES[spec.type](wrap, spec, defs);
    return { ...spec, wrap, node, phase: i * 1.7 };
  });
}
