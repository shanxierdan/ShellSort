# Experiment manifests

`discovery_manifest.json` defines the search validation and extrapolation panels.
`experiment_manifest.json` defines proof-constrained prefix tuning, independent
validation, the sealed test, and the broad final benchmark.  Search, validation,
and test use disjoint seeds.  The final benchmark contains five distributions at
five logarithmically spaced sizes with (10^7 < N \le 10^8).
