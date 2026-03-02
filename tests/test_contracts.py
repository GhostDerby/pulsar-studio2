"""
T-002: Contracts (Dataclasses) Unit Tests
Priority: P0 Critical
Component: src/shared/contracts.py
"""
import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shared.contracts import (
    JobSpec, SceneSpec, PricingSpec, RenderSpec, AudioSpec, JobResult,
)


# ── TC-002.1: JobSpec.to_dict() ─────────────────────────────────────

class TestJobSpecSerialization:
    def test_to_dict_is_serializable(self):
        """TC-002.1: JobSpec.to_dict() → JSON-serializable dict"""
        spec = JobSpec(
            job_id="job_test_001",
            product_name="Test Product",
            market="BR",
            mode="engineering",
            scenes=[SceneSpec(id=1, hook="HOOK", prompt="test prompt")],
        )
        d = spec.to_dict()
        assert isinstance(d, dict)
        # Must be JSON serializable without error
        json_str = json.dumps(d, ensure_ascii=False)
        assert '"job_test_001"' in json_str

    def test_roundtrip_json(self):
        """TC-002.2: Roundtrip: JobSpec → to_dict → JSON → dict → verify all fields"""
        scenes = [
            SceneSpec(id=1, hook="HOOK1", prompt="prompt 1", motion="zoom_in"),
            SceneSpec(id=2, hook="HOOK2", prompt="prompt 2", motion="orbit"),
        ]
        pricing = PricingSpec(currency="BRL", estimated_cogs=1.5, suggested_price=3.0, margin_target=0.5)
        spec = JobSpec(
            job_id="job_roundtrip",
            product_name="Roundtrip Product",
            market="US",
            mode="hollywood",
            scenes=scenes,
            pricing=pricing,
        )
        d = spec.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["job_id"] == "job_roundtrip"
        assert restored["product_name"] == "Roundtrip Product"
        assert restored["market"] == "US"
        assert restored["mode"] == "hollywood"
        assert len(restored["scenes"]) == 2
        assert restored["scenes"][0]["motion"] == "zoom_in"
        assert restored["pricing"]["currency"] == "BRL"
        assert restored["pricing"]["estimated_cogs"] == 1.5

    def test_all_fields_present(self):
        """to_dict() includes all top-level fields"""
        spec = JobSpec(
            job_id="j1", product_name="P", market="BR", mode="engineering",
            scenes=[SceneSpec(id=1, hook="H", prompt="p")],
        )
        d = spec.to_dict()
        required_keys = {"job_id", "product_name", "market", "mode", "scenes",
                         "render_spec", "audio_spec", "pricing"}
        assert required_keys.issubset(d.keys())


# ── TC-002.3: SceneSpec defaults ────────────────────────────────────

class TestSceneSpec:
    def test_default_motion(self):
        """TC-002.3: SceneSpec default motion is zoom_in"""
        scene = SceneSpec(id=1, hook="HOOK", prompt="test")
        assert scene.motion == "zoom_in"

    def test_custom_motion(self):
        scene = SceneSpec(id=2, hook="HOOK", prompt="test", motion="orbit")
        assert scene.motion == "orbit"

    def test_scene_fields(self):
        scene = SceneSpec(id=5, hook="ACTION", prompt="cinematic shot")
        assert scene.id == 5
        assert scene.hook == "ACTION"
        assert scene.prompt == "cinematic shot"


# ── TC-002.4: PricingSpec defaults ──────────────────────────────────

class TestPricingSpec:
    def test_defaults(self):
        """TC-002.4: PricingSpec defaults: currency=USD, margin=0.5"""
        p = PricingSpec()
        assert p.currency == "USD"
        assert p.estimated_cogs == 0.0
        assert p.suggested_price == 0.0
        assert p.margin_target == 0.5

    def test_custom_values(self):
        p = PricingSpec(currency="BRL", estimated_cogs=10.0, suggested_price=20.0, margin_target=0.6)
        assert p.currency == "BRL"
        assert p.margin_target == 0.6


# ── TC-002.5: RenderSpec defaults ───────────────────────────────────

class TestRenderSpec:
    def test_defaults(self):
        """TC-002.5: RenderSpec defaults: 1080×1920, 30fps, 3s"""
        r = RenderSpec()
        assert r.aspect == "9:16"
        assert r.width == 1080
        assert r.height == 1920
        assert r.fps == 30
        assert r.scene_seconds == 3


# ── TC-002.6: JobResult ─────────────────────────────────────────────

class TestJobResult:
    def test_to_dict_with_errors(self):
        """TC-002.6: JobResult.to_dict() with errors list"""
        result = JobResult(
            job_id="job_fail",
            status="failed",
            errors=["GPU OOM", "Timeout"],
        )
        d = result.to_dict()
        assert d["job_id"] == "job_fail"
        assert d["status"] == "failed"
        assert d["errors"] == ["GPU OOM", "Timeout"]
        assert d["final_video_uri"] is None
        assert d["artifacts"] == {}
        assert d["metrics"] == {}

    def test_success_result(self):
        result = JobResult(
            job_id="job_ok",
            status="success",
            final_video_uri="gs://bucket/video.mp4",
            artifacts={"frames": "gs://bucket/frames/"},
        )
        d = result.to_dict()
        assert d["status"] == "success"
        assert d["final_video_uri"] == "gs://bucket/video.mp4"
        assert "frames" in d["artifacts"]

    def test_serializable(self):
        result = JobResult(job_id="j", status="ok")
        json_str = json.dumps(result.to_dict())
        assert '"job_id"' in json_str
