# Dataset lineage maps

Interactive maps of where datasets come from and how they are reused, plus a shared knowledge base of dataset provenance, terms and consent. Every page is built from YAML by a small generic renderer and published with GitHub Pages from `docs/`.

## Maps

- [Data-cleaning benchmarks](docs/data-quality.html) (`data/maps/data-quality.yaml`): where the benchmark datasets used in data-cleaning papers (ADR, Raha, Baran, HoloClean, …) come from.
- [Data-cleaning and fairness benchmarks](docs/fair-data-quality.html) (`data/maps/fair-data-quality.yaml`): the same map extended with demodq (Guha et al., TKDE 2024) and its five datasets.
- [Face datasets](docs/face-image-datasets.html) (`data/maps/face-image-datasets.yaml`): where each face dataset's images came from, laid out by release year, with related publications that can be shown, greyed out or hidden.

Each map gets its own page: putting them all on one page would be too crowded to use. `docs/index.html` lists them.

## Knowledge base

[`docs/kb.html`](docs/kb.html) has one record per dataset across all maps (`data/kb.yaml`):
- Filter by topic (Faces, Data quality, Fairness), search every field, and sort the table. `kb.html?topic=faces` opens a filtered view.
- Click a record to see every field, its parent and derived datasets, and the maps it appears on.
- `kb.html#<id>` opens a record. Each map box's panel links to its record ("Knowledge base entry"), and each record links back to the box (`<map>.html#<id>`).

The face records were exported from the Face Dataset Provenance Knowledge Base on 2026-11-11. `data/kb.yaml` is now the source of truth.

Records of data-quality datasets hold only `id`, `name` and `topics`. Their facts (original source, path, sizes, where to get it) stay in the map YAML, because some of them differ per map. Adult's path, for example, gains demodq on the fairness map. The knowledge-base page gathers these facts from every map at build time.

Topics:
- `faces`: every face record.
- `data-quality`: every dataset on the data-cleaning maps.
- `fairness`: the five demodq datasets, plus face records whose Role includes "Fairness benchmark".

## Using a map

- **Trace a dataset.** Pick a pill in the "Trace a dataset" card, or a box in the left column of the map. Each left-column box is one original dataset: short name in bold, source underneath. The dataset is highlighted from its origin through every paper that used it, and the side panel shows its source, sizes, path and where to get it. Hovering previews the trace; clicking pins it.
- **Papers.** Hover over or tap a paper box to see what it took and what it passed on. Click to pin; click the background or press Esc to clear.
- "Show all line labels" names every line.
- Hover over a line to see the citing paper's own description of that dataset.
- Two tables sit below the map: one by dataset and one by paper or source.

- Add `#<box id>` to a map's address to open it with that box selected, e.g. `face-image-datasets.html#lfw`.

## Repository layout

- `data/maps/*.yaml`: one file per map; each becomes `docs/<name>.html`.
- `data/kb.yaml`: the knowledge base.
- `template/lineage.html` (map), `template/kb.html` (knowledge base) and `template/index.html` (index) are generic renderers, with no content of their own.
- `build.py` validates the YAML and writes self-contained pages.
- `docs/` holds the built site. It's committed so GitHub Pages can serve it as is. Don't edit it by hand.

## Building

Requires PyYAML (`pip install pyyaml`).

```
python build.py                 # whole site: every map, the knowledge base and the index, into docs/
python build.py --check         # validate everything, write nothing
python build.py data/maps/face-image-datasets.yaml face.html   # one standalone map page (no site links)
```

The build stops with an error for:
- unknown or duplicate ids
- links to unknown boxes or datasets
- a link whose `to` is a dataset rather than a paper
- columns out of range
- unknown kinds, statuses, link types, colours or topics
- knowledge-base relations that name unknown records

It warns about:
- boxes that overlap
- links that don't run left to right
- undeclared attributes or knowledge-base fields

It also notes map boxes with no knowledge-base record.

## Publishing

On GitHub: Settings → Pages → Build and deployment → Deploy from a branch → `main`, folder `/docs`. Rebuild and commit `docs/` after every data change.

## Knowledge-base schema

- **`topics`**: topic key → `label`. Topics appear as filter chips.
- **`fields`**: the record fields, in display order. Each has `key` and `label`. It may also have:
  - `table: true`: shown as a table column whenever a visible record has a value.
  - `type`: `list`, `ids` (other record ids, shown as links), `url` or `bool`.
- **`records`**: each has `id`, `name`, `topics` and any declared fields. `title`, `intro` and `footer` set the page text.

## Extending another map

A file can start with `extends: other.yaml` (a path relative to the file):
- Entries in `datasets`, `papers` or `nodes` whose `id` already exists patch the base entry field by field. New ids are appended.
- `links` are appended.
- `kinds`, `statuses`, `link_types`, `layout` and `links_legend` are merged.
- Other keys, such as `title` or `footer`, replace the base value.

`data/maps/fair-data-quality.yaml` uses this: it adds 4 datasets, 2 papers and 7 links, patches `adult` and `cleanml`, and replaces the footer.

## Map YAML schema

**Boxes**
- **`datasets`** (optional) are the traced left column, one entry per original dataset, in display order; each entry's position is its row. Fields:
  - `id`: the key used in links.
  - `name`: the bold label.
  - `source`: the subtitle.
  - `source_full`, `kind`, `url`.
  - Panel fields: `title` (if different from `name`), `aka`, `real`, `path`, `sizes`, `get`, `note`.

  Each dataset gets a "Trace a dataset" pill. Without `datasets`, the pills and the dataset table are hidden.
- **`papers`** / **`nodes`** are all other boxes; both lists work the same way. Fields:
  - `id`, `name`, `subtitle`, `full`, `kind` (default `paper`).
  - `column`: an index into `columns`.
  - `row` (may be fractional), or `y` in px, and optionally `x` in px.
  - `note`.
  - `created`: datasets introduced by that paper.
  - `status`: a key of `statuses`.
  - `attrs`: values for `node_fields`.
  - `url`, or `refs`: a list of `{label, short, url}`. `label` is shown in the panel, `short` in the table.
  - `kb`: the knowledge-base record for this box, when its id differs (e.g. `kb: cfd`), or `false` for boxes that aren't datasets. By default a box links to the record with its own id.

**Links**
- **`links`** run from the data source to the box that used it. Fields:
  - `from`, `to`.
  - `label`: shown on the line.
  - `datasets`: the keys this link carries. Required when the map has `datasets`; they drive the tracing.
  - `how`: a key of `link_types`; the default types are `paper` and `inferred`.
  - `note`: shown on hover.
  - Optional: `label_pos` (0–1 along the line), `label_dy` and `offset`.

**Styling and page text**
- **`kinds`** sets the colour categories: `label`, `legend`, and `color`, one of `series-1`–`series-4` or `neutral`. The legend shows only the kinds that are used.
- **`link_types`** (optional) sets the line styles. Each type has a `legend` and may have `dashed`, `tag` (shown after names, e.g. "(partly)") and `label` (text drawn on every line of that type). The default is `paper` (solid) and `inferred` (dashed, tag "inferred"). A type may also set `dotted`, `quiet` (faint until a connected box is selected) and `lineage: false`. Links of a `lineage: false` type, such as "covered in publication", are left out of the provenance chain, "Built from" and "Downstream". The panel lists them under `panel_out` and `panel_in` headings instead.
- **`statuses`** (optional) maps a status to a `badge` (e.g. ⊘), `dashed` (dashed border) and `legend`.
- **`node_fields`** (optional) lists the attributes shown in the panel: `key` and `label`.
- **`node_table`** (optional) sets the columns of the box table. Each column has `col` (`name`, `kind`, `status`, `year`, `field` with `key`, `from`, `to`, `linked` with `how`, or `links`) and `label`. **`node_table_title`** sets its heading.
- **`lanes`** (optional) are horizontal family bands: `label`, `y`, `h`, `label_y` (or `id` only, with `year_columns`). They replace the vertical column bands. Non-empty column labels are drawn as headers above the lanes.
- **`year_columns`** (optional) lays the map out by year, so no pixel positions are needed. Each entry has a `label` plus either `until` (the last year in that column) or `kinds` (a column for boxes of those kinds, e.g. publications). An entry with neither takes all later years. Each node then needs `year` (or `year_label` plus `place_year` for ranges and unknown years) and `lane` (a `lanes[].id`). `year_note` is shown in the panel. With `layout.auto_rows: true`, build.py picks the row of each box within its lane so that no lineage line passes behind another box; `lane_row` pins a box to a row. A line between two boxes in the same column is drawn vertically.
- **`toggles`** (optional) add Show / Grey out / Hide buttons for groups of kinds: `label`, `kinds` and `default` (`show`, `grey` or `hide`). Hiding removes the boxes, their lines, their table rows and their panel mentions, and narrows the drawing.
- **`panel: lineage`** shows a provenance chain, "Built from" and all downstream boxes, for maps where every box is a dataset. The default panel lists the datasets each box took and supplied.
- **`labels: always`** shows line labels without tracing.
- **`layout`** (colours are CSS variables at the top of the template, with a dark-mode set) may set `node_width`, `node_height`, `top`, `row_height`, `first_x`, `first_gap`, `col_gap`, `min_curve`, `width` and `height` (px), plus `min_width` (wider maps scroll sideways), `year_in_subtitle`, `lane_gap`, `lane_pad_top`, `lane_pad_bottom`, `auto_rows` and `auto_rows_restarts`.
- **`title`**, **`page_title`**, **`intro`**, **`svg_title`**, **`panel_hint`**, **`footer`** and **`links_legend`** set the page text. `intro`, `panel_hint` and `footer` may contain simple HTML.

## Notes on the data-cleaning maps

### Provenance traced from the papers

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

Sources: the full text of each paper on the map (including the published TKDE 2024 version of demodq), REIN (arXiv 2302.04702), CleanML (arXiv 1904.09483) and its DatasetDescriptions.pdf, and the BigDaMa/raha GitHub repository, read in November 2026. Download links come from the papers and were not re-checked.
