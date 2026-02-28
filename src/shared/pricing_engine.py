import logging
from dataclasses import dataclass

logger = logging.getLogger("FinOps")


@dataclass
class CostBreakdown:
    compute_cost: float
    ai_inference_cost: float
    storage_cost: float
    total_cogs: float
    suggested_price: float
    margin_percent: float
    currency: str = "USD"


class PricingEngine:
    """
    Simple, conservative budget estimator.
    Adjust constants based on your real invoices once you have them.
    """

    def __init__(self):
        self.RUN_COST_PER_SECOND = 0.00003
        self.GEMINI_REQUEST_COST = 0.002
        self.GPU_INFERENCE_COST_PER_IMAGE = 0.015
        self.FFMPEG_COST_PER_SCENE = 0.001
        self.BASE_OVERHEAD = 0.005

    def calculate_job_budget(self, mode: str, num_scenes: int, margin_target: float = 0.50) -> CostBreakdown:
        ai_cost = self.GEMINI_REQUEST_COST

        if mode == "hollywood":
            gpu_scenes = num_scenes
            cpu_scenes = 0
        elif mode == "engineering":
            gpu_scenes = 0
            cpu_scenes = num_scenes
        else:  # mixed
            gpu_scenes = int(num_scenes * 0.4)
            cpu_scenes = num_scenes - gpu_scenes

        ai_cost += (gpu_scenes * self.GPU_INFERENCE_COST_PER_IMAGE)

        est_duration = 10 + (gpu_scenes * 8) + (cpu_scenes * 2)
        compute_cost = est_duration * self.RUN_COST_PER_SECOND + (cpu_scenes * self.FFMPEG_COST_PER_SCENE)

        total_cogs = self.BASE_OVERHEAD + ai_cost + compute_cost

        if margin_target >= 1.0:
            margin_target = 0.99

        final_price = total_cogs / (1 - margin_target)

        return CostBreakdown(
            compute_cost=round(compute_cost, 5),
            ai_inference_cost=round(ai_cost, 5),
            storage_cost=self.BASE_OVERHEAD,
            total_cogs=round(total_cogs, 4),
            suggested_price=round(final_price, 2),
            margin_percent=round(margin_target * 100, 1),
        )
