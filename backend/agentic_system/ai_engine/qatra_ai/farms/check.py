"""Check every farm profile: `uv run python -m qatra_ai.farms.check`. Exit code 1 on errors."""

from __future__ import annotations

from qatra_ai.farms.registry import load_registry


def main() -> int:
    reg = load_registry()
    for farm_id, p in sorted(reg.profiles.items()):
        crops = ", ".join(sorted({z.crop for z in p.zones}))
        print(
            f"OK  {farm_id:20} {p.kind:5} {len(p.zones)} zone(s), {p.total_area_ha:g} ha, "
            f"{crops} | {p.location.latitude:.4f}, {p.location.longitude:.4f} "
            f"| {len(p.sensors)} sensor(s)  [{reg.sources[farm_id]}]"
        )
    for path, reason in sorted(reg.errors.items()):
        print(f"ERR {reason}  [{path}]")
    return 1 if reg.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
