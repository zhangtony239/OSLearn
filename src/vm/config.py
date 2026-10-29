"""vm-config.yaml handling: defaults, loading, validation, generation."""

from __future__ import annotations

import copy
import os
from typing import Any

import yaml

from .errors import ConfigError

CONFIG_FILENAME = "vm-config.yaml"

DEFAULTS: dict[str, Any] = {
    "version": 1,
    "scheduler": {
        "policy": "round_robin",  # round_robin | random
        "quantum": 5,  # statements per time slice (round_robin only)
        "seed": -1,  # -1 = fresh random seed, >=0 = reproducible
        "max_steps": 10000,  # hard stop for infinite loops
    },
    "language": {
        "lenient": True,  # tolerate pseudo-code statements / missing ';'
        "auto_declare": True,  # undefined variables default to 0
        "case_insensitive_keywords": True,
    },
    "trace": {
        "enabled": True,
        "stream": "stdout",  # stdout | stderr
    },
    "output": {
        "prefix": "",
    },
}

CONFIG_TEMPLATE = """\
# vm-config.yaml -- configuration for the `vm` pseudo-code runner.
# Run `vm config` to regenerate this file, or `vm config --force` to overwrite.

version: 1

scheduler:
  # round_robin: deterministic, each process runs `quantum` statements per turn
  # random:      pick a ready process at random for every step
  policy: round_robin
  quantum: 5
  # seed: -1 means "pick a random seed each run"; >= 0 makes runs reproducible
  seed: -1
  # hard stop so that `while (1)` snippets terminate
  max_steps: 10000

language:
  # tolerate textbook pseudo-code: natural-language statements, missing ';',
  # full-width punctuation, ellipses, ...
  lenient: true
  # undefined variables read as 0 and are created on first assignment
  auto_declare: true
  case_insensitive_keywords: true

trace:
  # print one line per executed statement / block / wake / exit
  enabled: true
  stream: stdout

output:
  prefix: ""
"""


def default_config() -> dict[str, Any]:
    return copy.deepcopy(DEFAULTS)


def _merge(dst: dict, src: dict) -> None:
    for key, value in src.items():
        if key not in dst:
            continue
        if isinstance(dst[key], dict) and isinstance(value, dict):
            _merge(dst[key], value)
        else:
            dst[key] = value


def load_config(path: str | None = None) -> dict[str, Any]:
    cfg = default_config()
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ConfigError(f"{path}: top level must be a mapping")
        _merge(cfg, data)
    return cfg


def validate(raw: Any) -> tuple[list[str], list[str]]:
    """Return ``(errors, warnings)`` for a parsed config mapping."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(raw, dict):
        return ["top level must be a mapping"], []

    for key in raw:
        if key not in DEFAULTS:
            warnings.append(f"unknown key: {key}")

    for section, spec in DEFAULTS.items():
        if section not in raw:
            warnings.append(f"missing key: {section} (using default)")
            continue
        value = raw[section]
        if isinstance(spec, dict):
            if not isinstance(value, dict):
                errors.append(f"{section}: expected a mapping")
                continue
            for key, default in spec.items():
                if key not in value:
                    warnings.append(f"missing key: {section}.{key} (using default)")
                    continue
                item = value[key]
                if isinstance(default, bool):
                    if not isinstance(item, bool):
                        errors.append(f"{section}.{key}: expected a boolean")
                elif isinstance(default, int):
                    if isinstance(item, bool) or not isinstance(item, int):
                        errors.append(f"{section}.{key}: expected an integer")
                elif isinstance(default, str):
                    if not isinstance(item, str):
                        errors.append(f"{section}.{key}: expected a string")
            for key in value:
                if key not in spec:
                    warnings.append(f"unknown key: {section}.{key}")
        else:
            if isinstance(spec, int) and not isinstance(spec, bool):
                if isinstance(value, bool) or not isinstance(value, int):
                    errors.append(f"{section}: expected an integer")

    policy = raw.get("scheduler", {}).get("policy") if isinstance(raw.get("scheduler"), dict) else None
    if policy is not None and policy not in ("round_robin", "random"):
        errors.append("scheduler.policy: must be 'round_robin' or 'random'")

    stream = raw.get("trace", {}).get("stream") if isinstance(raw.get("trace"), dict) else None
    if stream is not None and stream not in ("stdout", "stderr"):
        errors.append("trace.stream: must be 'stdout' or 'stderr'")

    quantum = raw.get("scheduler", {}).get("quantum") if isinstance(raw.get("scheduler"), dict) else None
    if isinstance(quantum, int) and not isinstance(quantum, bool) and quantum < 1:
        errors.append("scheduler.quantum: must be >= 1")

    max_steps = raw.get("scheduler", {}).get("max_steps") if isinstance(raw.get("scheduler"), dict) else None
    if isinstance(max_steps, int) and not isinstance(max_steps, bool) and max_steps < 1:
        errors.append("scheduler.max_steps: must be >= 1")

    return errors, warnings


def write_config(path: str, force: bool = False) -> bool:
    """Write the default config.  Returns False if it already exists."""
    if os.path.exists(path) and not force:
        return False
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(CONFIG_TEMPLATE)
    return True
