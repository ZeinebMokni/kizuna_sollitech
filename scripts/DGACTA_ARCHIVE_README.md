# Daily DGACTA archive

Run the archive once per day:

```powershell
cd ai_engine
uv run python ../scripts/dgacta_archive.py
```

The entry point downloads only current catalogue snapshots, preserves originals in
`data/raw/dgacta_sidi_bouzid/`, deduplicates identical SHA-256 content, rebuilds processed
tables, and exits non-zero on download or catalogue errors. A station with no observation newer
than 72 hours prints a stale-publication alert.
