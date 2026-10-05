// Shared SVG filters. Word filters work in font units (1000 per em), since
// the word paths are drawn in font units and scaled by their group.

const WORD_FILTERS = `
  <!-- Chiselled bevel. Stacking the glyph alpha eroded in 4-unit steps
       up to 60 font units (about half a stroke) gives a height map that
       rises straight from each edge to a sharp ridge along the stroke; lit
       from the upper left, the two slopes read as flat, hard-edged facets,
       bright toward the light and dark away from it. A blur of about one
       step hides the terracing while ridges and spiky terminals stay crisp. -->
  <filter id="bevel" x="-5%" y="-10%" width="110%" height="120%" color-interpolation-filters="sRGB">
    <feMorphology in="SourceAlpha" operator="erode" radius="4" result="e1"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="8" result="e2"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="12" result="e3"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="16" result="e4"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="20" result="e5"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="24" result="e6"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="28" result="e7"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="32" result="e8"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="36" result="e9"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="40" result="e10"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="44" result="e11"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="48" result="e12"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="52" result="e13"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="56" result="e14"/>
    <feMorphology in="SourceAlpha" operator="erode" radius="60" result="e15"/>
    <feComposite in="SourceAlpha" in2="e1" operator="arithmetic" k2="0.0625" k3="0.0625" result="h1"/>
    <feComposite in="h1" in2="e2" operator="arithmetic" k2="1" k3="0.0625" result="h2"/>
    <feComposite in="h2" in2="e3" operator="arithmetic" k2="1" k3="0.0625" result="h3"/>
    <feComposite in="h3" in2="e4" operator="arithmetic" k2="1" k3="0.0625" result="h4"/>
    <feComposite in="h4" in2="e5" operator="arithmetic" k2="1" k3="0.0625" result="h5"/>
    <feComposite in="h5" in2="e6" operator="arithmetic" k2="1" k3="0.0625" result="h6"/>
    <feComposite in="h6" in2="e7" operator="arithmetic" k2="1" k3="0.0625" result="h7"/>
    <feComposite in="h7" in2="e8" operator="arithmetic" k2="1" k3="0.0625" result="h8"/>
    <feComposite in="h8" in2="e9" operator="arithmetic" k2="1" k3="0.0625" result="h9"/>
    <feComposite in="h9" in2="e10" operator="arithmetic" k2="1" k3="0.0625" result="h10"/>
    <feComposite in="h10" in2="e11" operator="arithmetic" k2="1" k3="0.0625" result="h11"/>
    <feComposite in="h11" in2="e12" operator="arithmetic" k2="1" k3="0.0625" result="h12"/>
    <feComposite in="h12" in2="e13" operator="arithmetic" k2="1" k3="0.0625" result="h13"/>
    <feComposite in="h13" in2="e14" operator="arithmetic" k2="1" k3="0.0625" result="h14"/>
    <feComposite in="h14" in2="e15" operator="arithmetic" k2="1" k3="0.0625" result="h15"/>
    <feGaussianBlur in="h15" stdDeviation="3.5" result="height"/>
    <feDiffuseLighting in="height" surfaceScale="15" diffuseConstant="1.2" lighting-color="#ffffff" result="diffuse">
      <feDistantLight azimuth="225" elevation="44"/>
    </feDiffuseLighting>
    <feSpecularLighting in="height" surfaceScale="15" specularConstant="0.85" specularExponent="45"
        lighting-color="#ffffff" result="spec">
      <feDistantLight azimuth="225" elevation="44"/>
    </feSpecularLighting>
    <feComposite in="SourceGraphic" in2="diffuse" operator="arithmetic" k1="0.9" k2="0.35" result="lit"/>
    <feComposite in="spec" in2="SourceAlpha" operator="in" result="shine"/>
    <feComposite in="lit" in2="shine" operator="arithmetic" k2="1" k3="0.6" result="face"/>
    <feComposite in="face" in2="SourceAlpha" operator="in"/>
  </filter>

  <filter id="word-glow" x="-40%" y="-80%" width="180%" height="260%">
    <feGaussianBlur stdDeviation="95"/>
  </filter>

  <filter id="glint-soft" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="6"/>
  </filter>

  <radialGradient id="glint-ray">
    <stop offset="0" stop-color="#ffffff" stop-opacity="1"/>
    <stop offset="0.25" stop-color="#d9fbff" stop-opacity="0.6"/>
    <stop offset="1" stop-color="#9eeaff" stop-opacity="0"/>
  </radialGradient>
`;

const DECOR_FILTERS = `
  <!-- Shapes: fine glitter grain in the surface, plus halation around it. -->
  <!-- Frame-wide filter regions: a percentage of a thin shard's box would
       clip its bloom into visible rectangles. -->
  <filter id="edge-glow" filterUnits="userSpaceOnUse" x="-300" y="-300" width="2520" height="1680" color-interpolation-filters="sRGB">
    <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="1" seed="5" result="noise"/>
    <feColorMatrix in="noise" type="matrix" result="speck"
        values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  2.2 0 0 0 -1.3"/>
    <feComposite in="speck" in2="SourceAlpha" operator="in" result="glitter"/>
    <feComposite in="SourceGraphic" in2="glitter" operator="arithmetic" k2="1" k3="0.22" result="surface"/>
    <feGaussianBlur in="SourceGraphic" stdDeviation="16" result="halo"/>
    <feGaussianBlur in="SourceGraphic" stdDeviation="55" result="wide"/>
    <feComponentTransfer in="wide" result="bloom"><feFuncA type="linear" slope="0.5"/></feComponentTransfer>
    <feMerge><feMergeNode in="bloom"/><feMergeNode in="halo"/><feMergeNode in="surface"/></feMerge>
  </filter>

  <filter id="big-glow" filterUnits="userSpaceOnUse" x="-300" y="-300" width="2520" height="1680">
    <feGaussianBlur stdDeviation="40"/>
  </filter>

  <!-- Crinkled foil: lit noise multiplied into the fill. -->
  <filter id="foil" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
    <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="3" seed="11" result="noise"/>
    <feDiffuseLighting in="noise" surfaceScale="4" diffuseConstant="1.25" lighting-color="#ffffff" result="light">
      <feDistantLight azimuth="225" elevation="42"/>
    </feDiffuseLighting>
    <feComposite in="light" in2="SourceGraphic" operator="arithmetic" k1="1.15" k2="0" k3="0" k4="0" result="lit"/>
    <feComposite in="lit" in2="SourceAlpha" operator="in"/>
  </filter>

  <!-- Marbled flow for iridescent surfaces. -->
  <filter id="swirl" x="-20%" y="-20%" width="140%" height="140%">
    <feTurbulence type="fractalNoise" baseFrequency="0.006" numOctaves="2" seed="3" result="flow"/>
    <feDisplacementMap in="SourceGraphic" in2="flow" scale="260" xChannelSelector="R" yChannelSelector="G"/>
  </filter>

  <linearGradient id="holo-pink" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#fff0f7"/>
    <stop offset="0.35" stop-color="#ff86c8"/>
    <stop offset="0.65" stop-color="#e03aa8"/>
    <stop offset="1" stop-color="#6b3cf0"/>
  </linearGradient>

  <linearGradient id="holo-blue" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#2e9bff"/>
    <stop offset="0.4" stop-color="#7d7bff"/>
    <stop offset="0.7" stop-color="#ff86d2"/>
    <stop offset="1" stop-color="#fff6ee"/>
  </linearGradient>

  <linearGradient id="gold" x1="0" y1="0" x2="0.4" y2="1">
    <stop offset="0" stop-color="#fff2b8"/>
    <stop offset="0.45" stop-color="#e8c65a"/>
    <stop offset="1" stop-color="#a77d22"/>
  </linearGradient>

  <linearGradient id="iridescent" x1="0" y1="0" x2="0.3" y2="0.3" spreadMethod="reflect">
    <stop offset="0" stop-color="#9ff7e6"/>
    <stop offset="0.22" stop-color="#ffc2e4"/>
    <stop offset="0.42" stop-color="#fff2d4"/>
    <stop offset="0.62" stop-color="#8fe6ff"/>
    <stop offset="0.82" stop-color="#ffb3d6"/>
    <stop offset="1" stop-color="#c9fff0"/>
  </linearGradient>

  <radialGradient id="sphere-shade" cx="0.35" cy="0.3" r="0.75">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0.55"/>
    <stop offset="0.45" stop-color="#ffffff" stop-opacity="0"/>
    <stop offset="0.85" stop-color="#1a1030" stop-opacity="0.15"/>
    <stop offset="1" stop-color="#1a1030" stop-opacity="0.4"/>
  </radialGradient>

  <!-- Light-emitting look: a white-hot core screened over a shape. -->
  <radialGradient id="hotspot" cx="0.42" cy="0.4" r="0.55">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0.85"/>
    <stop offset="0.35" stop-color="#fff4f8" stop-opacity="0.35"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </radialGradient>

  <!-- Holographic sparkle: cyan-mint into pink into cream, diagonally. -->
  <linearGradient id="sparkle-fill" x1="0.85" y1="0.1" x2="0.15" y2="0.9">
    <stop offset="0" stop-color="#7fe9ff"/>
    <stop offset="0.3" stop-color="#bdf7e6"/>
    <stop offset="0.55" stop-color="#ffc9dc"/>
    <stop offset="0.8" stop-color="#fff2d2"/>
    <stop offset="1" stop-color="#e6fff4"/>
  </linearGradient>

  <filter id="beam-blur" filterUnits="userSpaceOnUse" x="-300" y="-300" width="600" height="600">
    <feGaussianBlur stdDeviation="9"/>
  </filter>

  <!-- Prism rays: a rainbow that fades out along the beam. -->
  <linearGradient id="prism-ray" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0.9"/>
    <stop offset="0.15" stop-color="#ff7ab8" stop-opacity="0.8"/>
    <stop offset="0.3" stop-color="#ffd66b" stop-opacity="0.7"/>
    <stop offset="0.45" stop-color="#7dffb0" stop-opacity="0.6"/>
    <stop offset="0.6" stop-color="#5fd8ff" stop-opacity="0.45"/>
    <stop offset="0.8" stop-color="#9a7bff" stop-opacity="0.2"/>
    <stop offset="1" stop-color="#9a7bff" stop-opacity="0"/>
  </linearGradient>

  <filter id="ray-blur" filterUnits="userSpaceOnUse" x="-300" y="-300" width="2520" height="1680">
    <feGaussianBlur stdDeviation="10"/>
  </filter>

  <!-- Ring strokes: cream-white on the left into mint and cyan on the
       right, as in the reference; and a pink variant. -->
  <linearGradient id="ring" x1="0" y1="0.5" x2="1" y2="0.5">
    <stop offset="0" stop-color="#fffbea"/>
    <stop offset="0.3" stop-color="#e4fff6"/>
    <stop offset="0.65" stop-color="#6fe6f0"/>
    <stop offset="1" stop-color="#2cc0e6"/>
  </linearGradient>

  <linearGradient id="ring-pink" x1="0" y1="0.5" x2="1" y2="0.5">
    <stop offset="0" stop-color="#fff0f4"/>
    <stop offset="0.5" stop-color="#ff86c8"/>
    <stop offset="1" stop-color="#8a63ff"/>
  </linearGradient>
`;

const SVG_NS = "http://www.w3.org/2000/svg";

/**
 * Shared filters and gradients, installed once in an always-rendered,
 * invisible SVG. They must not live inside a scene: url(#id) resolves to
 * the first element with that id in the page, and Chrome won't paint
 * filters or gradients from a hidden (inactive) scene's subtree.
 */
export function installSharedDefs() {
  const host = document.createElementNS(SVG_NS, "svg");
  host.setAttribute("class", "defs-host");
  host.setAttribute("aria-hidden", "true");
  host.setAttribute("width", "0");
  host.setAttribute("height", "0");
  const defs = document.createElementNS(SVG_NS, "defs");
  defs.insertAdjacentHTML("beforeend", WORD_FILTERS + DECOR_FILTERS);
  host.append(defs);
  document.body.prepend(host);
}

/** Per-scene defs, for elements with unique ids (word paths, clip paths). */
export function localDefs(svg) {
  return svg.insertBefore(document.createElementNS(SVG_NS, "defs"), svg.firstChild);
}
