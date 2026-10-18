# Frozen results

`discovery/` contains the validation-selected executable generators and the
finite numerical audits used while analyzing their geometric structure.

`final/` contains the proof-compatible prefix search, independent validation,
sealed test, and broad seven-baseline benchmark.  `final/selected.json` is the
authoritative machine-readable definition of the practical candidate, while
`final/benchmark.json` contains the task-level counts reported in the paper.

Generated checkpoints, SQLite caches, and logs are intentionally excluded.
