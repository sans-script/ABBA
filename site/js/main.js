import { installSharedDefs } from "./defs.js";
import { createFilm } from "./film.js";
import { createScene } from "./scene.js";
import { createSky } from "./sky.js";
import { reducedMotion } from "./util.js";

const [{ scenes: specs }, font] = await Promise.all([
  fetch("data/scenes.json").then((r) => r.json()),
  fetch("data/words.json").then((r) => r.json()),
]);

installSharedDefs();

const sky = createSky(document.getElementById("sky"));
const stages = document.getElementById("stages");
const film = createFilm(stages, document.getElementById("tone"));
const caption = document.getElementById("caption");
const progress = document.getElementById("progress");

// Review hook: ?scene=0&p=0.5 pins a scene at that share of its duration,
// for side-by-side comparison with reference frames; &t=1.2 also pins the
// animation clock (seconds) for ambient motion like twinkles and rings.
const params = new URLSearchParams(location.search);
const pinned = params.has("p")
  ? { scene: Number(params.get("scene") || 0), p: Number(params.get("p")) }
  : null;
const pinnedTime = params.has("t") ? Number(params.get("t")) : null;

const scenes = specs.map((spec, i) => createScene(spec, font, i, { stages }));

// The sequence plays like a video: scenes back to back with hard cuts,
// looping. Click or Space pauses.
const starts = [];
let total = 0;
for (const scene of scenes) {
  starts.push(total);
  total += scene.duration;
}

let playhead = 0;
let paused = false;
let last = null;
let current = -1;

function togglePause() {
  paused = !paused;
  document.body.classList.toggle("paused", paused);
}

document.addEventListener("click", togglePause);
document.addEventListener("keydown", (event) => {
  if (event.code === "Space") {
    event.preventDefault();
    togglePause();
  }
});

function sceneAt(t) {
  let i = scenes.length - 1;
  while (i > 0 && starts[i] > t) i--;
  return i;
}

function render(at, time) {
  sky.tick(time, at * 0.05);
  film.tick();

  let index;
  let elapsed;
  if (pinned) {
    index = pinned.scene;
    elapsed = pinned.p * scenes[index].duration;
  } else {
    index = sceneAt(at);
    elapsed = reducedMotion ? scenes[index].duration : at - starts[index];
  }

  if (index !== current) {
    scenes.forEach((scene, i) => scene.setActive(i === index));
    caption.textContent = scenes[index].text;
    current = index;
  }

  scenes[index].update(elapsed, time);
  const shown = pinned ? starts[index] + elapsed : at;
  progress.style.transform = `scaleX(${(shown / total).toFixed(4)})`;
}

// Capture mode (?capture): no clock of its own. tools/render_video.py calls
// seek(t) for every frame, which also sets the CSS-driven film layers
// (sheen, light leaks, grain) to t, so each frame is exact.
if (params.has("capture")) {
  document.body.classList.add("capture");
  window.videoDuration = total;
  window.seek = (t) => {
    for (const animation of document.getAnimations()) {
      animation.pause();
      animation.currentTime = t * 1000;
    }
    render(t % total, t);
  };
  window.seek(0);
} else {
  const frame = (now) => {
    const seconds = now / 1000;
    if (last !== null && !paused) playhead = (playhead + seconds - last) % total;
    last = seconds;
    render(playhead, pinnedTime ?? (reducedMotion ? 0 : seconds));
    requestAnimationFrame(frame);
  };
  frame(performance.now());
}
