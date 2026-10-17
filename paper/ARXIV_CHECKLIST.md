# arXiv release checklist

## Current status

The manuscript has passed the mathematical, experimental, bibliographic, and
clean-build checks.  The author block is set to Bo Liu, The Chinese University
of Hong Kong, Shenzhen, with the supplied institutional email address.

## Recommended metadata

- Primary category: `cs.DS` (Data Structures and Algorithms).
- Optional cross-list: `cs.LG` if the authors want the discovery system indexed
  by the machine-learning community.
- Title: *A New Gap Sequence for Shellsort: RL-Driven Algorithm Discovery
  Beyond N^(4/3)*.
- Comments: `25 pages; 2 tables; full proof and technical appendix.`
- License: choose explicitly in the arXiv submission form after confirming the
  authors' intended reuse policy.

The arXiv abstract field should use the prose from `abstract.tex` but omit the
displayed bound if the form rejects LaTeX display delimiters; write the same
bound inline instead.

## Source archive contents

The ready-to-upload archive is `shellsort-arxiv-source.tar.gz`. Its SHA-256 is
`28574dbac2af7f980c3e73dc524e6103954a140f5036d238dc1405b9f42a4c52`.
The corresponding `main.pdf` SHA-256 is
`42aa9d31ddb6fe072fdcd4201dc213a3d45eaf400ad5431795ca50fadb5a8361`.

Include only:

```text
main.tex
main.bbl
references.bib
abstract.tex
introduction.tex
method.tex
results.tex
theory_summary.tex
conclusion.tex
theory.tex
```

Do not include generated `.aux`, `.log`, `.out`, `.blg`, or `.pdf` files.  Also
exclude `camera-ready.tex`, `acmart.cls`, `ACM-Reference-Format.bst`, and the
downloaded ACM zip: none is used by `main.tex`.

## Checks completed

- Clean-directory compilation using only the files listed above.
- Bibliography generated without missing entries or warnings.
- No undefined references, overfull boxes, embedded JavaScript, or encryption.
- All fonts embedded in the generated PDF.
- All 85 project tests pass; the exact proof-completion tests also pass alone.
- Every value in the broad empirical table was recomputed from the frozen JSON.
- The 2026 Zang lower bound was checked against the current arXiv v2 and gives
  exactly the same polynomial exponent as the paper's upper bound.

After upload, inspect arXiv's generated PDF page by page before finalizing the
submission, as required by the arXiv submission workflow.
