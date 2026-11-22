"""Find and load farm profiles.

Shipped demo profiles live in the package; your own farms live in <data root>/farms/
(git-ignored). One YAML file per farm, named <farm_id>.yaml. An invalid file never stops the
others from loading: it is reported in `FarmRegistry.errors` with the reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from qatra_ai.data.store import data_root
from qatra_ai.farms.profile import FarmProfile

PACKAGE_FARMS_DIR = Path(__file__).resolve().parents[1] / "reference_data" / "farms"


class FarmProfileError(ValueError):
    pass


def user_farms_dir(root: Path | None = None) -> Path:
    return (root or data_root()) / "farms"


def load_profile(path: Path) -> FarmProfile:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise FarmProfileError(f"{path.name}: not valid YAML ({exc})") from exc
    if not isinstance(raw, dict):
        raise FarmProfileError(f"{path.name}: expected a mapping at the top level")
    try:
        profile = FarmProfile.model_validate(raw)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'profile'}: {e['msg']}" for e in exc.errors()
        )
        raise FarmProfileError(f"{path.name}: {problems}") from exc
    if path.stem != profile.farm_id:
        raise FarmProfileError(f"{path.name}: file name must be {profile.farm_id}.yaml")
    return profile


@dataclass
class FarmRegistry:
    profiles: dict[str, FarmProfile] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)  # file -> reason
    sources: dict[str, Path] = field(default_factory=dict)  # farm_id -> file

    def get(self, farm_id: str) -> FarmProfile:
        if farm_id not in self.profiles:
            raise KeyError(f"unknown farm {farm_id!r} (known: {', '.join(sorted(self.profiles))})")
        return self.profiles[farm_id]


def load_registry(dirs: list[Path] | None = None) -> FarmRegistry:
    """Load every *.yaml profile from the package demo folder and the user farms folder."""
    reg = FarmRegistry()
    for folder in dirs if dirs is not None else [PACKAGE_FARMS_DIR, user_farms_dir()]:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.yaml")):
            try:
                profile = load_profile(path)
            except FarmProfileError as exc:
                reg.errors[str(path)] = str(exc)
                continue
            if profile.farm_id in reg.profiles:
                reg.errors[str(path)] = (
                    f"{path.name}: farm_id {profile.farm_id!r} already defined in "
                    f"{reg.sources[profile.farm_id]}"
                )
                continue
            reg.profiles[profile.farm_id] = profile
            reg.sources[profile.farm_id] = path
    return reg
