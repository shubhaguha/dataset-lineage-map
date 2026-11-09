# Data quality dataset lineage

`data-quality-lineage.html` is an interactive map of where the benchmark datasets used in data-cleaning papers come from. It is self-contained; open it in any browser.

## Using it

- **Trace a dataset.** Pick a pill in the "Trace a dataset" card, or a box in the left column of the map. Each left-column box is one original dataset: short name in bold, source underneath. The dataset is highlighted from its origin through every paper that used it, and the side panel shows its source, sizes, path and where to get it. Hovering previews the trace; clicking pins it.
- **Papers.** Hover over or tap a paper box to see what it took and what it passed on. Click to pin; click the background or press Esc to clear.
- "Show all line labels" names every line.
- Hover over a line to see the citing paper's own description of that dataset.
- Two tables sit below the map: one by dataset and one by paper or source.

## Provenance traced from the papers

- BART's sources: Tax from Fan et al. (TODS 2008), Customers from Geerts et al. (ICDE 2014), Bus and Hospital from NADEEF.
- Holistic's CLIENT from Bertossi et al. (DBPL 2005). EMP is synthetic and created in Holistic.
- Truth finding's Flight data: 38 flight-status websites crawled in Dec 2011.
- Detecting data errors' five datasets: MIT VPF, Merck, Animal, Rayyan Bib, BlackOak.
- ADR's seven ML task datasets, one box each:
  - Through REIN (EDBT 2023): Adult (Kohavi 1996), Airfoil (NASA, UCI) and 3D Printer (Kaggle, Okudan 2019).
  - Through CleanML (ICDE 2021): Titanic (Kaggle) and Restaurant (Magellan repository, Yelp + Yellowpages).
  - Bank and Dress: ADR gives no source, and neither benchmark includes them.
- demodq (TKDE 2024, Guha et al.; extends the ICDE 2023 paper): five datasets, each cited from its public source.
  - adult: UCI.
  - folk: US Census ACS data via folktables (Retiring Adult, NeurIPS 2021), California 2018.
  - credit: Kaggle "Give Me Some Credit", the same data as CleanML's Credit.
  - german: UCI Statlog.
  - heart: Kaggle cardiovascular disease dataset.
  - TKDE builds on the CleanML benchmark code, not on its data.
- Inferred links (dashed), which the authors do not state:
  - Raha's IT is DDE's Merck table: same 2,262×61 shape and ~20% errors.
  - Raha's Rayyan is DDE's 1K-row ground-truth sample of Rayyan Bib.
  - Raha/Baran's proprietary Address may be DDE's BlackOak: same 94K×12 shape, but 14% vs 34% errors.
  - REIN → ADR and CleanML → ADR: ADR only says it picked its ML datasets "following previous related works", citing REIN and CleanML among others.

## Repository layout

- `data/data-quality.yaml` holds all the content: page text, columns, colour kinds, datasets, papers and links.
- `template/lineage.html` is the generic renderer: styles, layout and interactions, with no map content.
- `build.py` validates the YAML and writes the self-contained page.
- `data-quality-lineage.html` is the built page. It's committed so it can be opened or published as is. Don't edit it by hand.

## Editing

Edit `data/data-quality.yaml`, then rebuild (requires PyYAML: `pip install pyyaml`):

```
python build.py data/data-quality.yaml data-quality-lineage.html
python build.py data/data-quality.yaml --check     # validate only
```

The build stops with an error for:
- unknown or duplicate ids
- links to unknown boxes or datasets
- a link whose `to` is a dataset rather than a paper
- columns out of range
- unknown kinds or colours

It warns about:
- boxes that overlap in a column
- links that don't run left to right
- datasets no link uses

The YAML has these parts:

- **`datasets`** is the left column, one entry per original dataset, in display order; each entry's position is its row. Fields:
  - `id`: the key used in links.
  - `name`: the bold label.
  - `source`: the subtitle.
  - `source_full`, `kind`, `url`.
  - Panel fields: `title` (if different from `name`), `aka`, `real`, `path`, `sizes`, `get`, `note`.

  Each dataset gets a "Trace a dataset" pill automatically.
- **`papers`** are all the other boxes. Fields:
  - `id`, `name`, `subtitle`, `full`, `url`, `note`.
  - `column`: an index into `columns`, at least 1.
  - `row`: may be fractional.
  - `created`: a list of datasets introduced by that paper.
- **`links`** run from the data source to the paper that used it. Fields:
  - `from`, `to`.
  - `label`: shown on the line.
  - `datasets`: the keys this link carries; these drive the tracing.
  - `how`: `paper` (stated in the citing paper) or `inferred` (drawn dashed).
  - `note`: the citing paper's own description, shown on hover.
  - Optional: `label_pos` (0–1 along the line), `label_dy` and `offset`.
- **`kinds`** sets the colour categories: `label`, `legend`, and `color`, one of `series-1`–`series-4` or `neutral`. The legend shows only the kinds that are used.
- **`title`**, **`intro`**, **`panel_hint`**, **`footer`** and **`links_legend`** set the page text. `intro`, `panel_hint` and `footer` may contain simple HTML.

Columns are 220 px apart, with extra room after the first column. Rows are 58 px apart. The colours are CSS variables at the top of the template, with a separate dark-mode set.

Sources: the full text of each paper on the map (including the published TKDE 2024 version of demodq), REIN (arXiv 2302.04702), CleanML (arXiv 1904.09483) and its DatasetDescriptions.pdf, and the BigDaMa/raha GitHub repository, read in November 2026. Download links come from the papers and were not re-checked.
