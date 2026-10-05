export const SVG_NS = "http://www.w3.org/2000/svg";

export const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
export const lerp = (a, b, t) => a + (b - a) * t;
export const easeOutCubic = (t) => 1 - (1 - t) ** 3;
export const easeInOutSine = (t) => -(Math.cos(Math.PI * t) - 1) / 2;

export const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

export function el(name, attrs = {}, parent) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (parent) parent.appendChild(node);
  return node;
}

let counter = 0;
export const uid = (prefix) => `${prefix}-${++counter}`;

/** Deterministic random numbers, so layouts are stable between visits. */
export function seeded(seed) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

/** Mix two #rrggbb colors. */
export function mix(a, b, t) {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const channel = (shift) =>
    Math.round(lerp((pa >> shift) & 255, (pb >> shift) & 255, t));
  return `rgb(${channel(16)} ${channel(8)} ${channel(0)})`;
}
