from __future__ import annotations

import tomllib
from pathlib import Path

_DEFAULTS_PATH = Path(__file__).parent / "defaults.toml"

with open(_DEFAULTS_PATH, "rb") as _f:
    DEFAULTS = tomllib.load(_f)

T_DEAD_S: float = DEFAULTS["switching"]["t_dead_s"]
T_AMB_C: float = DEFAULTS["thermal"]["T_amb_C"]
TJ_ASSUMED_C: float = DEFAULTS["thermal"]["Tj_assumed_C"]
