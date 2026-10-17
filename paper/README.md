# Paper workspace

This directory contains the full manuscript and the separate ACM production
wrapper.  The arXiv manuscript includes the final author and affiliation block
in `main.tex`.

## Which file to write

- `main.tex` is the default full manuscript: US Letter, 11-point font, single
  column, single spacing, at least 1-inch margins, and a separate title page.
- `outline.md` records the paper-level argument, section plan, empirical claim,
  and exact scope of the $N^{4/3}$ comparison.
- `abstract.tex`, `introduction.tex`, `method.tex`, `results.tex`,
  `theory_summary.tex`, `theory.tex`, and `conclusion.tex` are the shared
  manuscript modules.  `theory_summary.tex` keeps the main proof within the
  presentation-page budget; `theory.tex` contains the full technical proof in
  the appendix.  Both wrappers include the same files.
- `camera-ready.tex` is only for the **accepted version**. It uses ACM's
  `sigconf` proceedings layout. Do not use it for the anonymous submission.
- `references.bib` is the bibliography database shared by the manuscript.
- `acmart.cls` and `ACM-Reference-Format.bst` are the local production files
  used to compile the camera-ready template without relying on an older class
  bundled with the TeX environment.
- `acmart-2.19.zip` is the complete production `acmart` package downloaded
  from CTAN. Version 2.19 is newer than the `acmart` 2.16 minimum specified by
  the STOC 2026 camera-ready instructions.

The next STOC call should be checked before submission in case formatting or
page-limit rules change. The current reference pages are:

- STOC 2026 call for papers: <https://acm-stoc.org/stoc2026/stoc2026-cfp.html>
- ACM proceedings templates: <https://www.acm.org/publications/proceedings-template>
- CTAN production release of `acmart`: <https://ctan.org/pkg/acmart>

Downloaded archive SHA-256:

```text
5011d4a698b993ffd4c9a6a24cf4cde7dc9deb4a7ec2dc357dbbe4ec15085618  acmart-2.19.zip
```

## Build

The `pytorch` conda environment contains Tectonic. Compile with:

```bash
cd paper
make
```

This builds `main.pdf`. Run `make camera-ready` only when preparing the final
ACM version. `make clean` removes generated LaTeX files. Both templates have
also been compiled locally with this environment.

## Submission checklist

- Confirm that the author names, order, affiliation, email, and arXiv metadata
  form all agree before finalizing the release.
- Write self-citations in the third person.
- Keep the first 12 content pages after the title page suitable for a broad
  theory audience; put extra technical detail afterward if needed.
- Use a symbolic bibliography style such as `alpha` (already selected in
  `main.tex`).
- Add ACM rights and conference metadata to `camera-ready.tex` only after ACM
  sends the accepted-paper metadata.
