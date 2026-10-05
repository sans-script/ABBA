// Film finish over the whole page, matched to the reference: lifted teal
// blacks (empty sky ~ rgb 11 23 29), soft optics, colored grain (sky std
// ~7 levels), gentle gate weave and flicker; plus the holographic post
// layer on top (bloom, sheen, light leaks, scanlines, grain; style.css).
// ?film=0 turns it all off for side-by-side checks.

import { reducedMotion } from "./util.js";

export const FILM = {
  softness: 0.6,   // px of blur at 1080p, scaled with the viewport
  contrast: 1,
  saturate: 1.22,
  brightness: 1,
  weave: 0.5,      // px of frame wobble at 1080p
  flicker: 0.025,  // brightness jitter
  postSoft: 0.45,  // px of softness over everything at 1080p
  bloom: 22,       // px bloom radius at 1080p
};

function grainTile(size = 192) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(size, size);
  for (let i = 0; i < image.data.length; i += 4) {
    const v = Math.random() * 255;
    image.data[i] = image.data[i + 1] = image.data[i + 2] = v;
    image.data[i + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);
  return `url(${canvas.toDataURL()})`;
}

export function createFilm(stages, tone) {
  const enabled = new URLSearchParams(location.search).get("film") !== "0";
  document.body.classList.toggle("no-film", !enabled);
  if (!enabled) return { tick() {} };

  // ?post=bloom,sheen keeps only those post layers (soft, bloom, sheen,
  // leak, scan, grain), for comparing them one by one.
  const keep = new URLSearchParams(location.search).get("post");
  if (keep !== null) {
    const wanted = keep.split(",");
    for (const layer of document.querySelectorAll(".post > div")) {
      layer.hidden = !wanted.includes(layer.className.replace("post-", ""));
    }
  }

  const root = document.documentElement.style;
  root.setProperty("--grain-tile", grainTile());

  let scale = 1;
  const resize = () => {
    scale = window.innerHeight / 1080;
    // Softness only on decor (see style.css); the lettering stays sharp.
    stages.style.setProperty("--film-blur", `${(FILM.softness * scale).toFixed(2)}px`);
    stages.style.filter =
      `contrast(${FILM.contrast}) saturate(${FILM.saturate}) brightness(${FILM.brightness})`;
    root.setProperty("--post-soft", `${(FILM.postSoft * scale).toFixed(2)}px`);
    root.setProperty("--post-bloom", `${(FILM.bloom * scale).toFixed(1)}px`);
  };
  window.addEventListener("resize", resize);
  resize();

  let frame = 0;
  return {
    tick() {
      if (reducedMotion || frame++ % 2) return;
      const w = FILM.weave * scale;
      stages.style.translate = `${((Math.random() - 0.5) * w).toFixed(2)}px ${((Math.random() - 0.5) * w).toFixed(2)}px`;
      tone.style.opacity = (1 - FILM.flicker + Math.random() * FILM.flicker * 2).toFixed(3);
    },
  };
}
