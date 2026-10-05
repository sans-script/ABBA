# Motion Graphics Decomposition

Tool to split flat animated videos into separate graphical assets.

## Workflow

```bash
pip install -r requirements.txt
python scripts/download.py                             # media/ (gitignored, local study only)
python src/extractor.py --scenes --contact-sheet       # analysis/: cuts + overview
python src/prepare_fsd.py --name <clip> --start 53.68 --end 55.68            # preview.jpg
python src/prepare_fsd.py --name <clip> --start 53.68 --end 55.68 \
    --box x0,y0,x1,y1@54.8 ...                         # one box per sprite, source px
```

FSD needs a GPU: upload `analysis/fsd/inputs/<clip>/` to Drive and run
`notebooks/fsd_colab.ipynb` on Colab (setup steps are in the notebook).
Keep each clip inside a single shot: FSD assumes no cuts.
