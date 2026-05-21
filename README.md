# Qiuqi Wang Website

This site is built with Jekyll, which is supported directly by GitHub Pages.

## Updating Content

Most routine edits are in `_pages/`:

- `_pages/publications.yml` for papers and links
- `_pages/teaching.yml` for courses
- `_pages/activities.yml` for invited presentations, conference presentations, and organization
- `_pages/visits.yml` for academic visits
- `_pages/awards.yml` for honors and awards
- `_pages/education.yml` and `_pages/appointment.yml` for background entries
- `_pages/service.yml` for peer review service
- `_pages/site.yml` for contact details and profile links
- `files/Curriculum_Vitae.pdf` is the only CV PDF to replace when updating the CV

Jekyll still refers to these files as `site.data.*` because `_config.yml` sets `data_dir: _pages`.

The `google-sublinks/` folder contains redirect pages for old Google sitelinks such as `/cv/`, `/teaching/`, and `/publications/`. They stay grouped there in the source repo, but Jekyll still publishes them at the correct public URLs.

The page layout is in `index.html`. The visual design is in `assets/css/site.css`, and the small navigation script is in `assets/js/site.js`.

## Updating Publications Automatically

The publication list lives in `_pages/publications.yml`. To refresh metadata from DOI and arXiv links, run:

```bash
python3 -m pip install -r requirements-publications.txt
python3 scripts/update_publications.py --write
```

By default, the updater only fills blank `title`, `authors`, or `venue` fields. To refresh existing fields from DOI/arXiv metadata, run:

```bash
python3 scripts/update_publications.py --write --mode refresh
```

For a new paper, add a small entry in `_pages/publications.yml` with its `number` and either a DOI link or arXiv link, then run the updater. GitHub also has an **Update publications** workflow that can run manually or weekly and open a pull request when metadata changes.

## Previewing Locally

Install Jekyll once if it is not already installed:

```bash
gem install jekyll bundler
```

Then run this from the project folder:

```bash
jekyll serve
```

Open `http://127.0.0.1:4000/`. GitHub Pages will build the site automatically after pushing changes.
