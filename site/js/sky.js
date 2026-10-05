// Fixed backdrop shared by every scene: dark starfield, soft nebula glows
// (cyan, violet, pink) and animated film grain. Grain lives in the sky
// only: lettering stays clean, shapes carry their own glitter grain.

import { reducedMotion, seeded } from "./util.js";

const NEBULAE = [
  { x: 0.18, y: 0.28, r: 0.55, color: [40, 170, 200], alpha: 0.18 },
  { x: 0.82, y: 0.78, r: 0.6, color: [120, 60, 190], alpha: 0.1 },
  { x: 0.68, y: 0.12, r: 0.45, color: [230, 80, 160], alpha: 0.05 },
  { x: 0.35, y: 0.9, r: 0.5, color: [60, 90, 200], alpha: 0.1 },
];

const STAR_TINTS = ["255 255 255", "200 245 255", "255 225 240", "255 245 215"];

const GRAIN_OPACITY = 0.07;

export function createSky(canvas) {
  const ctx = canvas.getContext("2d");
  const backdrop = document.createElement("canvas");
  const noise = document.createElement("canvas");
  noise.width = noise.height = 128;

  let stars = [];
  let width = 0;
  let height = 0;
  let dpr = 1;

  function paintBackdrop() {
    backdrop.width = width * dpr;
    backdrop.height = height * dpr;
    const b = backdrop.getContext("2d");
    b.scale(dpr, dpr);

    const base = b.createLinearGradient(0, 0, 0, height);
    base.addColorStop(0, "#03090d");
    base.addColorStop(1, "#020609");
    b.fillStyle = base;
    b.fillRect(0, 0, width, height);

    const size = Math.max(width, height);
    b.globalCompositeOperation = "lighter";
    for (const n of NEBULAE) {
      const g = b.createRadialGradient(n.x * width, n.y * height, 0, n.x * width, n.y * height, n.r * size);
      g.addColorStop(0, `rgb(${n.color.join(" ")} / ${n.alpha})`);
      g.addColorStop(1, "rgb(0 0 0 / 0)");
      b.fillStyle = g;
      b.fillRect(0, 0, width, height);
    }

    // Faint dust: many very dim static points.
    const random = seeded(7);
    for (let i = 0; i < (width * height) / 900; i++) {
      b.fillStyle = `rgb(255 255 255 / ${0.04 + random() * 0.08})`;
      b.fillRect(random() * width, random() * height, 1, 1);
    }
    b.globalCompositeOperation = "source-over";
  }

  function makeStars() {
    const random = seeded(42);
    stars = Array.from({ length: Math.round((width * height) / 1100) }, () => {
      const big = random() ** 6;
      return {
        x: random(),
        y: random(),
        r: 0.4 + big * 1.8,
        alpha: 0.35 + random() * 0.65,
        speed: 0.6 + random() * 2.2,
        phase: random() * Math.PI * 2,
        tint: STAR_TINTS[Math.floor(random() * STAR_TINTS.length)],
      };
    });
  }

  function resize() {
    dpr = Math.min(2, window.devicePixelRatio || 1);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    paintBackdrop();
    makeStars();
    draw(0);
  }

  let grain = null;
  let grainOffset = [0, 0];

  function makeGrain() {
    const n = noise.getContext("2d");
    const image = n.createImageData(noise.width, noise.height);
    for (let i = 0; i < image.data.length; i += 4) {
      const v = Math.random() * 255;
      image.data[i] = v + (Math.random() - 0.5) * 70;
      image.data[i + 1] = v + (Math.random() - 0.5) * 70;
      image.data[i + 2] = v + (Math.random() - 0.5) * 70;
      image.data[i + 3] = 255;
    }
    n.putImageData(image, 0, 0);
    grain = ctx.createPattern(noise, "repeat");
    grainOffset = [Math.random() * 128, Math.random() * 128];
  }

  function draw(time, drift = 0) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(backdrop, 0, 0);
    ctx.scale(dpr, dpr);

    for (const s of stars) {
      const twinkle = reducedMotion ? 1 : 0.65 + 0.35 * Math.sin(time * s.speed + s.phase);
      const y = (((s.y - drift * s.r * 0.02) % 1) + 1) % 1;
      ctx.fillStyle = `rgb(${s.tint} / ${s.alpha * twinkle})`;
      if (s.r < 1) {
        ctx.fillRect(s.x * width, y * height, s.r * 1.4, s.r * 1.4);
      } else {
        ctx.beginPath();
        ctx.arc(s.x * width, y * height, s.r, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    if (grain && !reducedMotion) {
      ctx.setTransform(1.6 * dpr, 0, 0, 1.6 * dpr, 0, 0);
      ctx.translate(grainOffset[0], grainOffset[1]);
      ctx.globalAlpha = GRAIN_OPACITY;
      ctx.fillStyle = grain;
      ctx.fillRect(-128, -128, width + 256, height + 256);
      ctx.globalAlpha = 1;
    }
  }

  let frame = 0;
  function tick(time, drift) {
    if (!reducedMotion && frame++ % 3 === 0) makeGrain();
    draw(time, drift);
  }

  window.addEventListener("resize", resize);
  makeGrain();
  resize();

  return { tick };
}
