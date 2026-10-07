"""YAML config plus environment secrets.

Secrets are read only from the environment. A local ``.env`` file is loaded
if python-dotenv is unavailable we parse it ourselves, and only for keys
that are not already set. The file is never required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def load_dotenv(path: str | Path = ".env") -> None:
    file_path = Path(path)
    if not file_path.exists():
        return
    for raw in file_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _deep_update(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


@dataclass
class AppConfig:
    raw: dict[str, Any]
    path: str

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.raw
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    @property
    def live_trading_enabled(self) -> bool:
        return bool(self.get("live_trading_enabled", default=False))

    @property
    def allow_unproven_strategies(self) -> bool:
        return bool(self.get("allow_unproven_strategies", default=False))


def load_config(path: str | os.PathLike[str] = "config/default.yaml") -> AppConfig:
    load_dotenv()
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Config not found: {file_path}")
    raw = yaml.safe_load(file_path.read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError("Config root must be a mapping")
    return AppConfig(raw=raw, path=str(file_path))


@dataclass
class RiskSettings:
    risk_per_trade: float = 0.0075
    max_position_pct: float = 0.20
    max_concurrent_positions: int = 5
    max_sector_pct: float = 0.35
    max_correlation: float = 0.85
    correlation_lookback: int = 60
    daily_max_loss_pct: float = 0.02
    max_drawdown_pct: float = 0.15
    flatten_on_daily_loss: bool = True
    flatten_on_max_drawdown: bool = False
    intraday_margin_ratio: float = 0.25
    min_margin_equity: float = 2000.0
    allow_shorts: bool = False
    allow_fractional: bool = False

    @classmethod
    def from_config(cls, config: AppConfig) -> "RiskSettings":
        block = config.get("risk", default={}) or {}
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in block.items() if k in known})


@dataclass
class PdtSettings:
    mode: str = "auto"  # auto | on | off
    enforce_legacy_during_transition: bool = True
    legacy_equity_threshold: float = 25_000.0
    legacy_max_day_trades: int = 3
    legacy_window_business_days: int = 5

    @classmethod
    def from_config(cls, config: AppConfig) -> "PdtSettings":
        block = config.get("pdt", default={}) or {}
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in block.items() if k in known})


@dataclass
class CostSettings:
    commission_per_trade: float = 0.0
    slippage_bps: float = 5.0
    half_spread_bps: float = 1.0
    sec_fee_per_dollar_sold: float = 20.60 / 1_000_000
    finra_taf_per_share: float = 0.000195
    finra_taf_cap: float = 9.79

    @classmethod
    def from_config(cls, config: AppConfig) -> "CostSettings":
        block = config.get("costs", default={}) or {}
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in block.items() if k in known})


def cost_model_from_config(config: AppConfig):
    from webull_bot.costs import CostModel

    settings = CostSettings.from_config(config)
    return CostModel(**settings.__dict__)
