# No Bugs, Just Vibes

A short synth-pop "lyric video" written in plain HTML/CSS/JS, in an early-80s
holographic art style: bevelled gold-to-cyan script lettering, holographic
shards, iridescent spheres, expanding rings, sparkles, lightning and prism
rays, under a film finish (bloom, grain, scanlines, light leaks). All lines
and layouts are original.

## Run it

```bash
pip install -r requirements.txt
python tools/build_words.py                 # font -> site/data/words.json (kerned, joined outlines)
python -m http.server 8123 -d site          # open http://127.0.0.1:8123/
```

The page plays the scenes back to back with hard cuts and loops; click or
press Space to pause. The font file itself is never served: words are
drawn from SVG outlines built from it.

- `site/data/scenes.json` — lines, timing (`duration`, s), tilt, decor layout per scene
- `site/js/scene.js` — timing and placement rules
- `site/js/word.js`, `site/js/defs.js` — bevelled lettering and shared filters
- `site/js/decor.js` — shape library and layouts
- `site/js/film.js`, `site/style.css` — film and holographic finish

Review hooks: `?scene=3&p=0.5&t=1.2` pins a frame, `?film=0` turns the
finish off, `?post=bloom,grain` keeps only those finish layers.

## Render the video

```bash
python tools/render_video.py                # renders/no-bugs-just-vibes.mp4
```

Steps the timeline frame by frame in headless Chrome and encodes with the
ffmpeg bundled by `imageio-ffmpeg`.

## Reference study

`scripts/download.py` and `src/extractor.py` pull frames from a reference
video for local study only (`media/` and `analysis/` are gitignored).
