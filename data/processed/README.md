# processed/

Real observations parsed from `raw/` into the long-format schema (see `data/README.md`). One folder per source.

- Allowed data classes: measured, official, farmer_reported, remote_sensed, inferred. **Simulated rows are rejected.**
- Every row names the SHA-256 of the raw file it came from.
- Bad values are kept as published and flagged (`invalid`, `suspect`), never changed or dropped.
