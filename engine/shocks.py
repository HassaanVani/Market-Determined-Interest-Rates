from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Shock:
    shock_id: str
    shock_type: str
    start_period: int
    duration: int
    magnitude: float
    target_id: str = "aggregate"

    @property
    def end_period(self):
        return self.start_period + self.duration - 1

    def is_active(self, period):
        return self.start_period <= period <= self.end_period

    def to_dict(self):
        return asdict(self)


class ShockEngine:
    def __init__(self, model, shocks=None):
        self.model = model
        self.shocks = list(shocks or [])

    def effects(self, period):
        effects = {
            "demand_multiplier": 1.0,
            "credit_demand_multiplier": 1.0,
            "productivity_multiplier": 1.0,
            "expected_inflation_shift": 0.0,
        }
        for shock in self.shocks:
            if not shock.is_active(period):
                continue
            if shock.shock_type == "demand":
                effects["demand_multiplier"] *= 1.0 + shock.magnitude
                effects["credit_demand_multiplier"] *= 1.0 + shock.magnitude
            elif shock.shock_type == "productivity":
                effects["productivity_multiplier"] *= 1.0 + shock.magnitude
                effects["credit_demand_multiplier"] *= 1.0 + 0.5 * shock.magnitude
            elif shock.shock_type == "inflation_expectation":
                effects["expected_inflation_shift"] += shock.magnitude
        return effects
