from dataclasses import dataclass, field
from enum import StrEnum

from backend.app.services.benchmarks.logger import BenchmarkMetrics


class PromotionDecision(StrEnum):
    promote = "promote"
    retry = "retry"
    reject = "reject"


@dataclass(frozen=True)
class PromotionGateConfig:
    max_peak_vram_mib: int = 23000
    max_failure_rate: float = 0.2


@dataclass(frozen=True)
class PromotionGateResult:
    decision: PromotionDecision
    reasons: list[str] = field(default_factory=list)


class PromotionGateEvaluator:
    def __init__(self, config: PromotionGateConfig | None = None) -> None:
        self.config = config or PromotionGateConfig()

    def evaluate(self, metrics: BenchmarkMetrics) -> PromotionGateResult:
        reasons: list[str] = []
        if metrics.peak_vram_mib is not None and metrics.peak_vram_mib >= self.config.max_peak_vram_mib:
            reasons.append(
                f"peak_vram_mib {metrics.peak_vram_mib} is at or above limit {self.config.max_peak_vram_mib}"
            )
        if metrics.failure_rate is not None and metrics.failure_rate > self.config.max_failure_rate:
            reasons.append(
                f"failure_rate {metrics.failure_rate:.3f} exceeds limit {self.config.max_failure_rate:.3f}"
            )
        if reasons:
            return PromotionGateResult(PromotionDecision.reject, reasons)

        if not metrics.complete:
            return PromotionGateResult(PromotionDecision.retry, ["benchmark metrics are incomplete"])

        return PromotionGateResult(PromotionDecision.promote, ["benchmark metrics satisfy promotion gates"])
