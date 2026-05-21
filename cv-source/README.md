# CV Source

`Curriculum_Vitae.tex` is generated from the website YAML files by:

```bash
ruby scripts/build_cv.rb
```

The generated PDF is written to `files/Curriculum_Vitae.pdf`, which is the only CV PDF used by the website.

Most recurring CV content comes from `_pages/*.yml`, so updating publications, teaching, activities, visits, service, or contact details updates both the website and the CV after rebuilding.
