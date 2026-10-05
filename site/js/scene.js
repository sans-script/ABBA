// A scene: full-screen stage (decor + words) that plays from 0 s when it
// cuts in; the sequence and cuts are run by main.js.

import { localDefs } from "./defs.js";
import { buildDecor } from "./decor.js";
import { buildWord } from "./word.js";
import { clamp, easeInOutSine, easeOutCubic, el, uid } from "./util.js";

// Timing rules, in seconds from the cut. Measured from the reference
// (53.64-55.0 s): the first word cuts in with the shot, the rest arrive
// one by one across ~1.4 s, each fading in over ~4 frames (some revealed
// left to right), then keep brightening; the whole frame slowly pushes in.
export const RULES = {
  arrival: 1.4,   // s over which a line's words arrive
  fade: 0.16,     // s per-word fade-in
  writeOn: 0.45,  // s left-to-right reveal for words listed in writeOn
  settle: 1.0,    // s the glow keeps brightening after arrival
  pushIn: 0.07,   // camera scale gained across the scene's duration
  pop: 0.06,      // words grow by this much while fading in
};

// Placement rules, in font units (1000 per em).
const LINE_HEIGHT = 0.95;  // em
const WORD_GAP = 1.15;     // x the font's space width
const TEXT_TOP = -0.8;     // em above baseline covered by a word's box
const TEXT_BOTTOM = 0.25;  // em below baseline
const FIT_WIDTH = 0.5;    // share of the 1920 frame the text block spans

export function createScene(spec, font, index, { stages }) {
  const em = font.unitsPerEm;

  const stage = document.createElement("div");
  stage.className = "stage";
  stage.hidden = true;
  stage.setAttribute("aria-hidden", "true");
  stages.append(stage);

  // Decor fills the screen (cropped on narrow screens); lyrics always fit.
  const decorSvg = el("svg", { class: "layer decor", viewBox: "0 0 1920 1080", preserveAspectRatio: "xMidYMid slice" });
  const lyricSvg = el("svg", { class: "layer", preserveAspectRatio: "xMidYMid meet" });
  stage.append(decorSvg, lyricSvg);

  const decorDefs = localDefs(decorSvg);
  const lyricDefs = localDefs(lyricSvg);

  const decorCamera = el("g", {}, decorSvg);
  const shapes = buildDecor(decorDefs, decorCamera, spec.decor);

  const lyricCamera = el("g", {}, lyricSvg);
  const fit = el("g", {}, lyricCamera);

  // Layout: rows stacked, each row shifted right by rowShift x first row width.
  const gap = font.space * WORD_GAP;
  const rowWidth = (line) =>
    line.reduce((w, word, i) => w + font.words[word].advance + (i ? gap : 0), 0);
  const shift = spec.rowShift * rowWidth(spec.lines[0]);

  const words = [];
  let order = 0;
  let contentRight = 0;

  spec.lines.forEach((line, row) => {
    let x = row * shift;
    for (const text of line) {
      const outline = font.words[text];
      const slot = el("g", { transform: `translate(${x} ${row * LINE_HEIGHT * em})` }, fit);
      const word = buildWord(lyricDefs, slot, outline, order, 1000 * (index + 1) + order);

      const box = { x: 0, y: TEXT_TOP * em, width: outline.advance, height: (TEXT_BOTTOM - TEXT_TOP) * em };
      const glints = word.placeGlints(box);

      const writeOn = (spec.writeOn || []).includes(text);
      let clip = null;
      if (writeOn) {
        const clipId = uid("reveal");
        const clipPath = el("clipPath", { id: clipId, clipPathUnits: "userSpaceOnUse" }, lyricDefs);
        clip = el("rect", { x: -60, y: -1.4 * em, height: 3 * em, width: 0 }, clipPath);
        word.body.setAttribute("clip-path", `url(#${clipId})`);
      }

      words.push({ ...word, text, order, glints, writeOn, clip, center: [outline.advance / 2, -0.3 * em] });
      contentRight = Math.max(contentRight, x + outline.advance + word.depth[0]);
      x += outline.advance + gap;
      order += 1;
    }
  });

  const content = {
    x: 0,
    y: TEXT_TOP * em,
    width: contentRight,
    height: (spec.lines.length - 1) * LINE_HEIGHT * em + (TEXT_BOTTOM - TEXT_TOP) * em + words[0].depth[1],
  };

  // Timeline: first word is there from the cut; the rest spread evenly.
  const n = words.length;
  for (const word of words) {
    word.duration = word.writeOn ? RULES.writeOn : RULES.fade;
    word.start = word.order === 0 ? -word.duration : (word.order / (n - 1)) * RULES.arrival;
  }

  let frameWidth = 1920;

  function layout() {
    frameWidth = 1080 * (window.innerWidth / window.innerHeight);
    lyricSvg.setAttribute("viewBox", `0 0 ${frameWidth} 1080`);
    const target = Math.min(FIT_WIDTH * 1920, 0.86 * frameWidth);
    const scale = target / content.width;
    const cx = content.x + content.width / 2;
    const cy = content.y + content.height / 2;
    fit.setAttribute(
      "transform",
      `translate(${frameWidth / 2} 540) rotate(${spec.tilt}) scale(${scale}) translate(${-cx} ${-cy})`,
    );
  }

  layout();
  window.addEventListener("resize", layout);

  const duration = spec.duration;

  function update(elapsed, time) {
    const p = clamp(elapsed / duration);
    const zoom = 1 + RULES.pushIn * easeInOutSine(p);
    decorCamera.setAttribute("transform", `translate(960 540) scale(${zoom}) translate(-960 -540)`);
    lyricCamera.setAttribute(
      "transform",
      `translate(${frameWidth / 2} 540) scale(${zoom}) translate(${-frameWidth / 2} -540)`,
    );

    for (const word of words) {
      const a = clamp((elapsed - word.start) / word.duration);
      const shown = word.writeOn ? clamp(a * 4) : easeOutCubic(a);
      const grow = 1 - RULES.pop + RULES.pop * easeOutCubic(a);
      const [cx, cy] = word.center;
      word.group.setAttribute("opacity", shown.toFixed(3));
      word.group.setAttribute(
        "transform",
        `translate(${cx} ${cy}) scale(${grow.toFixed(4)}) translate(${-cx} ${-cy})`,
      );

      if (word.clip) {
        word.clip.setAttribute("width", ((word.advance + word.depth[0] + 120) * easeInOutSine(a)).toFixed(1));
      }

      const settled = clamp((elapsed - word.start) / RULES.settle);
      word.glow.setAttribute("opacity", (0.08 + 0.12 * settled).toFixed(3));

      for (const glint of word.glints) {
        const pulse = 0.55 + 0.45 * Math.sin(time * 1.4 + glint.phase);
        glint.node.setAttribute("opacity", (settled * pulse).toFixed(3));
        glint.node.setAttribute(
          "transform",
          `translate(${glint.x} ${glint.y}) scale(${(0.75 + 0.35 * pulse).toFixed(3)})`,
        );
      }
    }

    for (const shape of shapes) {
      const dx = (p - 0.5) * shape.depth * -46;
      const dy = (p - 0.5) * shape.depth * 26;
      shape.wrap.setAttribute("transform", `translate(${dx.toFixed(2)} ${dy.toFixed(2)})`);

      if (shape.type === "sparkle") {
        const s = 0.92 + 0.1 * Math.sin(time * 1.8 + shape.phase);
        shape.node.inner.setAttribute("transform", `scale(${s.toFixed(3)})`);
      } else if (shape.type === "sphere") {
        const [cx, cy] = shape.node.center;
        shape.node.flow.setAttribute("transform", `rotate(${(time * 8).toFixed(2)} ${cx} ${cy})`);
      } else if (shape.node.update) {
        shape.node.update(time + shape.phase);
      }
    }
  }

  return {
    stage,
    duration,
    text: spec.lines.map((line) => line.join(" ")).join(" / "),
    update,
    setActive(active) {
      stage.hidden = !active;
    },
  };
}
