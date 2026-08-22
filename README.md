# Testing Pedestrian Flow and Delay Estimation from First-Actuation Latency

Data and code archive for:

Levinson, D. (2026). Testing Pedestrian Flow and Delay Estimation from First-Actuation Latency. *Findings*, August 20, 2026. https://doi.org/10.32866/001c.166369

## Status

This repository contains the releasable data, code, manifests, checksums, and derived outputs used for the paper's first-actuation validation analyses. Raw SCATS controller histories are not included.

## Contents

- `Pedestrian Actuators Validation Project/Manual Crossing-Actuation Validation/11_Intersections_Data.xlsx`: Manual Crossing-Actuation Validation (MCAV) workbook used for the field validation.
- `broad_results/validation/mcav_validation/`: MCAV normalizer script, data dictionary, normalized cycle/case outputs, model comparison outputs, leave-one-out results, plot data, and compliance-scenario outputs.
- `broad_results/validation/video_noncompliance_validation/`: peer video-validation scripts and outputs using the upstream Choy and Levinson video-coded pedestrian data package.
- `broad_results/validation/video_noncompliance_validation/source/choy_final_data_20260720/`: checksum-verified upstream video inputs used by the peer-validation script.
- `documentation/`: final manuscript source evidence, references, and figure source used to verify the data/code availability statement and reported figure.
- `paper/`: local reference copies of the Findings article and supplemental information. These are included for audit convenience and remain governed by the publisher's terms.
- `PACKAGE_MANIFEST.csv`: package file inventory with SHA-256 checksums.
- `EXCLUDED_NONARCHIVAL_MANIFEST.csv`: explicit exclusions and rationale.

## Reproduction

Run the MCAV validation from the repository root with a Python environment that includes `openpyxl`:

```sh
python3 broad_results/validation/mcav_validation/scripts/normalize_mcav_validation.py
```

Run the primary video peer validation from the repository root:

```sh
python3 broad_results/validation/video_noncompliance_validation/scripts/estimate_video_upstream_peer.py
```

The video peer-validation script uses only Python's standard library. The MCAV normalizer uses `openpyxl` to read the Excel workbook; it was verified with the bundled Codex workspace Python runtime on 2026-08-23.

## Paper-Data Match

The article reports:

- MCAV: 14 crossing-direction cases, 1,744 pedestrians, 513 actuations, 492 restrictive cycles, and 14.07 hours of exposure.
- Video peer dataset: 2,003 mapped pedestrians in 24 leg-session cases after excluding one observation without a mapped physical leg.
- Data and code availability: public video archive associated with Choy and Levinson (2026), plus reproducible scripts, input manifests, checksums, manual validation data, and derived case outputs.

This package includes those releasable components and preserves the original validation-folder layout so the scripts can resolve inputs by their original relative paths.

## Release Boundary

Included:

- author-created validation scripts;
- MCAV manual validation workbook and normalized derived outputs;
- Choy-derived peer-validation input files needed for this paper's peer test;
- manifests, checksums, data dictionaries, and paper-facing derived outputs.

Excluded:

- raw SCATS controller histories and broader SCATS HST source dumps;
- unrelated Site 516 temporal-profile material from a different paper workflow;
- vendored Python environments, LaTeX build products, logs, scratch files, and review-only material.

## License

Author-created code in this repository is licensed under MIT. Repository documentation and derived data are licensed under CC BY 4.0. Third-party or publisher material is not relicensed here; see `LICENSE_STATUS.md`.
