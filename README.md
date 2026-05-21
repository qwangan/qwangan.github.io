# Qiuqi Wang Website

This site is built with Jekyll, which is supported directly by GitHub Pages.

## Updating Content

Most routine edits are in `_data/`:

- `_data/publications.yml` for papers and links
- `_data/teaching.yml` for courses
- `_data/activities.yml` for invited presentations, conference presentations, and organization
- `_data/visits.yml` for academic visits
- `_data/awards.yml` for honors and awards
- `_data/education.yml` and `_data/appointment.yml` for background entries
- `_data/service.yml` for peer review service
- `_data/site.yml` for contact details and profile links

The page layout is in `index.html`. The visual design is in `assets/css/site.css`, and the small navigation script is in `assets/js/site.js`.

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
