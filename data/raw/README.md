# raw/

Downloaded files exactly as the publisher served them. One folder per source (`raw/<source>/`).

- **Never edit** a file here. Corrections happen in `processed/` as QC flags.
- File names start with the first 12 hex digits of the file's SHA-256, so each new snapshot of the same URL is kept beside the older ones.
- Each file has a `<file>.manifest.json`: URL, publisher, retrieval time (UTC), licence, data class and SHA-256. `verify_raw()` checks a file against it.
- **Simulated data is never stored here.**
- Written only through `qatra_ai.data.store.write_raw`.
