from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import uuid


class RateRegime(str, Enum):
    ADMINISTERED = "administered"
    MARKET = "market"


class BehaviorMode(str, Enum):
    RULE = "rule"
    LLM = "llm"


@dataclass(frozen=True)
class SeedBundle:
    environment: int = 0
    matching: int = 1
    shocks: int = 2
    behavior: int = 3


@dataclass(frozen=True)
class ExperimentConfig:
    """Versioned description of one experimental condition.

    Rate formation and actor behavior are deliberately independent fields. The
    current legacy engine does not yet implement every combination; the config
    exists now so new results cannot silently conflate the two treatments.
    """

    specification_version: str = "0.2"
    source_fingerprint: str = "unrecorded"
    scenario_name: str = "baseline"
    rate_regime: RateRegime = RateRegime.MARKET
    behavior_mode: BehaviorMode = BehaviorMode.LLM
    n_firms: int = 5
    n_banks: int = 2
    horizon: int = 10
    llm_model: str = "deepseek-r1:8b"
    llm_temperature: float = 0.7
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    llm_max_tokens: int = 256
    llm_reasoning_effort: str = "none"
    prompt_version: str = "0.1"
    agent_sentiment: str = "neutral"
    reserve_requirement: float = 0.10
    capital_requirement: float = 0.08
    leverage_limit: float = 1.5
    policy_rate: float = 0.03
    initial_reserves_per_bank: float = 1000.0
    initial_bank_equity: float = 100.0
    lender_of_last_resort: str = "unavailable"
    emergency_penalty_spread: float = 0.02
    emergency_borrowing_limit_ratio: float = 1.0
    heterogeneity_scale: float = 0.0
    shocks: tuple = field(default_factory=tuple)
    seeds: SeedBundle = field(default_factory=SeedBundle)

    def to_dict(self):
        values = asdict(self)
        values["rate_regime"] = self.rate_regime.value
        values["behavior_mode"] = self.behavior_mode.value
        return values

    def canonical_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def fingerprint(self):
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()[:16]


def new_run_id(config: ExperimentConfig):
    return f"{config.fingerprint()}-{uuid.uuid4().hex[:12]}"
