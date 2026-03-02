"""
T-001: PricingEngine Unit Tests
Priority: P0 Critical
Component: src/shared/pricing_engine.py
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shared.pricing_engine import PricingEngine, CostBreakdown


@pytest.fixture
def engine():
    return PricingEngine()


# ── TC-001.1: engineering mode ──────────────────────────────────────

class TestEngineeringMode:
    def test_engineering_no_gpu(self, engine):
        """TC-001.1: engineering mode → gpu_scenes=0, cpu_scenes=3"""
        result = engine.calculate_job_budget("engineering", 3, 0.50)
        # engineering → no GPU cost, only FFMPEG + base
        assert result.ai_inference_cost == round(engine.GEMINI_REQUEST_COST, 5)
        assert result.total_cogs > 0
        assert result.suggested_price > result.total_cogs

    def test_engineering_price(self, engine):
        result = engine.calculate_job_budget("engineering", 3, 0.50)
        assert isinstance(result, CostBreakdown)
        assert result.currency == "USD"
        assert result.margin_percent == 50.0


# ── TC-001.2: hollywood mode ───────────────────────────────────────

class TestHollywoodMode:
    def test_hollywood_uses_gpu(self, engine):
        """TC-001.2: hollywood mode → gpu_scenes=3, cpu_scenes=0"""
        result = engine.calculate_job_budget("hollywood", 3, 0.60)
        expected_ai = round(engine.GEMINI_REQUEST_COST + 3 * engine.GPU_INFERENCE_COST_PER_IMAGE, 5)
        assert result.ai_inference_cost == expected_ai

    def test_hollywood_more_expensive(self, engine):
        """TC-001.3 (implicit): hollywood > engineering"""
        eng = engine.calculate_job_budget("engineering", 3, 0.50)
        hol = engine.calculate_job_budget("hollywood", 3, 0.60)
        assert hol.suggested_price > eng.suggested_price


# ── TC-001.3: mixed mode ───────────────────────────────────────────

class TestMixedMode:
    def test_mixed_splits_scenes(self, engine):
        """TC-001.3: mixed mode, 5 scenes → gpu=2, cpu=3"""
        result = engine.calculate_job_budget("mixed", 5, 0.50)
        expected_ai = round(engine.GEMINI_REQUEST_COST + 2 * engine.GPU_INFERENCE_COST_PER_IMAGE, 5)
        assert result.ai_inference_cost == expected_ai


# ── TC-001.4/5: margin edge cases ──────────────────────────────────

class TestMarginEdgeCases:
    def test_margin_099(self, engine):
        """TC-001.4: margin=0.99 → finite price, not infinity"""
        result = engine.calculate_job_budget("engineering", 3, 0.99)
        assert result.suggested_price < 1000
        assert result.suggested_price > 0

    def test_margin_100_capped(self, engine):
        """TC-001.5: margin=1.0 → capped to 0.99, no division by zero"""
        result = engine.calculate_job_budget("engineering", 3, 1.0)
        assert result.suggested_price > 0
        assert result.suggested_price < 10000

    def test_margin_zero(self, engine):
        """margin=0 → price >= cogs (ceil rounding)"""
        result = engine.calculate_job_budget("engineering", 3, 0.0)
        assert result.suggested_price >= result.total_cogs

    def test_negative_margin(self, engine):
        """negative margin → price < cogs (loss leader)"""
        result = engine.calculate_job_budget("engineering", 3, -0.5)
        assert result.suggested_price > 0


# ── TC-001.6/7: scene count edge cases ─────────────────────────────

class TestSceneEdgeCases:
    def test_zero_scenes(self, engine):
        """TC-001.6: 0 scenes → no crash, valid result"""
        result = engine.calculate_job_budget("engineering", 0, 0.50)
        assert isinstance(result, CostBreakdown)
        assert result.total_cogs > 0  # still has base overhead

    def test_many_scenes(self, engine):
        """TC-001.7: 100 scenes → correct, linear scaling"""
        r10 = engine.calculate_job_budget("hollywood", 10, 0.50)
        r100 = engine.calculate_job_budget("hollywood", 100, 0.50)
        assert r100.suggested_price > r10.suggested_price
        # roughly 10× more expensive with 10× scenes
        ratio = r100.total_cogs / r10.total_cogs
        assert 5 < ratio < 15


# ── TC-001.8/9: invariants ─────────────────────────────────────────

class TestInvariants:
    @pytest.mark.parametrize("mode", ["engineering", "hollywood", "mixed"])
    @pytest.mark.parametrize("scenes", [1, 3, 5, 10])
    @pytest.mark.parametrize("margin", [0.1, 0.3, 0.5, 0.7, 0.9])
    def test_price_exceeds_cogs(self, engine, mode, scenes, margin):
        """TC-001.8: suggested_price > total_cogs (always, when margin > 0)"""
        result = engine.calculate_job_budget(mode, scenes, margin)
        assert result.suggested_price >= result.total_cogs

    @pytest.mark.parametrize("mode", ["engineering", "hollywood", "mixed"])
    def test_all_fields_non_negative(self, engine, mode):
        """TC-001.9: all CostBreakdown fields >= 0"""
        result = engine.calculate_job_budget(mode, 3, 0.50)
        assert result.compute_cost >= 0
        assert result.ai_inference_cost >= 0
        assert result.storage_cost >= 0
        assert result.total_cogs >= 0
        assert result.suggested_price >= 0
        assert result.margin_percent >= 0
