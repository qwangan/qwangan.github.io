# Qiuqi Wang Website

This site is built with Jekyll, which is supported directly by GitHub Pages.

## Updating Content

Most routine edits are in `_pages/`:

- `_pages/publications.yml` for papers and links
- `_pages/teaching.yml` for courses
- `_pages/activities.yml` for invited presentations, conference presentations, and organization
- `_pages/visits.yml` for academic visits
- `_pages/editorial_service.yml` for editorial service
- `_pages/awards.yml` for honors and awards
- `_pages/education.yml` and `_pages/appointment.yml` for background entries
- `_pages/service.yml` for peer review service
- `_pages/site.yml` for contact details and profile links
- `files/Curriculum_Vitae.pdf` is the only CV PDF to replace when updating the CV

Jekyll still refers to these files as `site.data.*` because `_config.yml` sets `data_dir: _pages`.

The `google-sublinks/` folder contains redirect pages for old Google sitelinks such as `/cv/`, `/teaching/`, and `/publications/`. They stay grouped there in the source repo, but Jekyll still publishes them at the correct public URLs.

The page layout is in `index.html`. The visual design is in `assets/css/site.css`, and the small navigation script is in `assets/js/site.js`.

## Updating the CV

The website uses one CV PDF: `files/Curriculum_Vitae.pdf`. The CV is generated from the same YAML files that power the website for recurring sections such as publications, teaching, activities, visits, editorial service, service, contact details, and research interests.

Academic Appointment, Education, Professional Designation, and Honors & Awards are intentionally CV-only and live in `cv-source/static/`; updating `_pages/appointment.yml`, `_pages/education.yml`, or `_pages/awards.yml` changes the website but does not change the CV.

To rebuild the CV locally:

```bash
ruby scripts/build_cv.rb
```

To build a draft without replacing the public PDF:

```bash
ruby scripts/build_cv.rb --draft-output
```

On GitHub, the **Build CV PDF** workflow rebuilds and commits `files/Curriculum_Vitae.pdf` when shared website data changes. The publication updater explicitly dispatches it after bot commits, because ordinary push triggers are suppressed for `GITHUB_TOKEN` commits. The CV builder also explicitly requests a GitHub Pages build so the new PDF is published. It does not watch `_pages/appointment.yml`, `_pages/education.yml`, or `_pages/awards.yml`.

## Updating Publications Automatically

The publication list lives in `_pages/publications.yml`. The **Update publications** workflow runs **daily at 09:37 UTC** (05:37 Eastern during daylight saving time; 04:37 in winter). It discovers new arXiv and SSRN papers, fills missing metadata, finalizes provisional journal details, and commits changes. Scheduled GitHub jobs can run late.

Author identity and companion-paper mappings are configured in `publication-sources.yml`. arXiv discovery searches the full author name and checks every result's authors. SSRN discovery uses SSRN's publisher-deposited Crossref DOI records, filtering by ORCID and exact full name. This avoids SSRN's restrictions on automated HTML access. SSRN papers become discoverable after their DOI metadata is deposited and indexed by Crossref; that delay is controlled by SSRN/Crossref and has no guaranteed duration.

Discovery matches existing papers by source identifier or normalized title, adds arXiv/SSRN links to existing journal entries, and assigns stable P-numbers to genuinely new manuscripts. Related material can be mapped to a parent paper; the SSRN simulation companion to E-backtesting is linked under J10. Existing author/title capitalization and journal citations are retained in the default `missing` mode. Genuine title or author changes can be accepted using a manual `refresh` run.

After a changed list is committed, the workflow **explicitly requests a Pages build and dispatches the CV builder**. This is required because commits made with `GITHUB_TOKEN` do not trigger ordinary Pages builds or push workflows. Both writers use one concurrency group and check out the latest branch when starting, so a queued run does not push from an outdated event commit. If a source fails, successful updates are retained and published, and the workflow finishes with a visible failure instead of silently reporting success.

To discover papers and refresh metadata locally:

```bash
python3 -m pip install -r requirements-publications.txt
python3 scripts/update_publications.py --write --discover --fail-on-error
```

To refresh metadata for existing entries without discovering papers, omit `--discover`. By default, the updater fills blank `title`, `authors`, or `venue` fields and replaces provisional venue text such as `available online` once DOI metadata has final volume/issue/page details. To explicitly refresh all existing fields from DOI/arXiv/SSRN metadata, run:

```bash
python3 scripts/update_publications.py --write --mode refresh
```

You can still add a paper manually using its `number` and a DOI, arXiv, or SSRN link. Run without `--write` to preview proposed changes. Offline regression checks run with `python3 -m unittest discover -s tests -v`.

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
