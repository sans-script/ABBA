# ABBA fan tribute — reference study

Local tools for studying the visual language of the "Lay All Your Love On Me"
lyric video, as reference for an original scroll-driven tribute site.

```bash
pip install -r requirements.txt
python scripts/download.py                          # media/ (gitignored, local study only)
python src/extractor.py --scenes --contact-sheet    # analysis/: cuts + overview
python src/extractor.py --start 53.6 --end 55.7 --all   # every frame of one transition
```
