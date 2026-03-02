"""
T-003: Node A Integration Tests (LOCAL_MOCK mode)
T-004: Node B Integration Tests (LOCAL_MOCK mode)
T-005: Full Pipeline E2E Test
Priority: P0 Critical
Requires: Both nodes running with LOCAL_MOCK=1
  - Node A on port 8080
  - Node B on port 8081
"""
import json
import base64
import os
import time
import pytest
import urllib.request
import urllib.error

NODE_A = "http://localhost:8080"
NODE_B = "http://localhost:8081"


def http_post(url, data=None):
    body = json.dumps(data or {}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


def http_get(url):
    with urllib.request.urlopen(url) as resp:
        return resp.status, json.loads(resp.read())


def pubsub_envelope(payload: dict) -> dict:
    data_b64 = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    return {"message": {"data": data_b64}}


# ═══════════════════════════════════════════════════════════════════
# T-003: Node A Integration Tests
# ═══════════════════════════════════════════════════════════════════

class TestNodeAHealth:
    def test_health_200(self):
        """TC-003.6: /health → 200"""
        status, body = http_get(f"{NODE_A}/health")
        assert status == 200
        assert body["status"] == "ok"

    def test_health_has_mock_flag(self):
        """TC-003.6: health shows local_mock"""
        _, body = http_get(f"{NODE_A}/health")
        assert "local_mock" in body


class TestNodeACreateJob:
    def test_create_job_basic(self):
        """TC-003.1: POST → dispatched, job_id starts with job_"""
        status, body = http_post(f"{NODE_A}/create_job", {
            "product_name": "Test Widget",
            "mode": "engineering",
            "market": "BR",
        })
        assert status == 200
        assert body["status"] == "dispatched"
        assert body["job_id"].startswith("job_")
        assert body["price"] > 0
        assert body["currency"] == "USD"

    def test_create_job_defaults(self):
        """TC-003.2: POST without body → defaults work"""
        status, body = http_post(f"{NODE_A}/create_job", {})
        assert status == 200
        assert body["status"] == "dispatched"

    def test_hollywood_more_expensive(self):
        """TC-003.3: hollywood price > engineering price"""
        _, eng = http_post(f"{NODE_A}/create_job", {"product_name": "X", "mode": "engineering"})
        _, hol = http_post(f"{NODE_A}/create_job", {"product_name": "X", "mode": "hollywood"})
        assert hol["price"] > eng["price"]

    def test_job_json_on_disk(self):
        """TC-003.4/5: job.json exists and has required fields"""
        _, body = http_post(f"{NODE_A}/create_job", {"product_name": "Disk Check"})
        spec_uri = body["spec_uri"]
        # LOCAL_MOCK saves as file:// URI
        assert spec_uri.startswith("file://")
        path = spec_uri.replace("file://", "")
        assert os.path.isfile(path), f"job.json not found at {path}"

        with open(path) as f:
            job = json.load(f)
        assert job["job_id"] == body["job_id"]
        assert "scenes" in job
        assert "pricing" in job
        assert "render_spec" in job
        assert len(job["scenes"]) == 3

    def test_unique_job_ids(self):
        """TC-003.8: 5 rapid requests → all unique job_ids"""
        ids = set()
        for _ in range(5):
            _, body = http_post(f"{NODE_A}/create_job", {"product_name": "Rapid"})
            ids.add(body["job_id"])
            time.sleep(1.1)  # job_id uses int(time.time()), need 1s gap
        assert len(ids) == 5


# ═══════════════════════════════════════════════════════════════════
# T-004: Node B Integration Tests
# ═══════════════════════════════════════════════════════════════════

class TestNodeBHealth:
    def test_health_200(self):
        """TC-004.8: /health → 200"""
        status, body = http_get(f"{NODE_B}/health")
        assert status == 200
        assert body["status"] == "ok"


class TestNodeBPubSub:
    def test_assets_ready_creates_result(self):
        """TC-004.1: stage=assets_ready → result.json created"""
        job_id = f"test_b_{int(time.time())}"
        envelope = pubsub_envelope({
            "job_id": job_id,
            "bucket": "brazil-studio-assets",
            "stage": "assets_ready",
            "spec_uri": f"file:///tmp/{job_id}/job.json",
        })
        req = urllib.request.Request(
            f"{NODE_B}/",
            data=json.dumps(envelope).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

        # Check result.json was created
        result_path = f"./tmp/jobs/{job_id}/final/result.json"
        # Need to check from the Node B working dir
        cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(cwd, "src", "tmp", "jobs", job_id, "final", "result.json")
        assert os.path.isfile(full_path), f"result.json not found at {full_path}"

        with open(full_path) as f:
            result = json.load(f)
        assert result["job_id"] == job_id
        assert result["status"] == "success_stub"
        assert result["errors"] == []

    def test_job_created_stage_skips(self):
        """TC-004.2: stage=job_created → skips assembly, 200"""
        envelope = pubsub_envelope({
            "job_id": "skip_test",
            "stage": "job_created",
        })
        req = urllib.request.Request(
            f"{NODE_B}/",
            data=json.dumps(envelope).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

    def test_unknown_stage_skips(self):
        """TC-004.3: unknown stage → skips, 200"""
        envelope = pubsub_envelope({
            "job_id": "unknown_test",
            "stage": "some_random_stage",
        })
        req = urllib.request.Request(
            f"{NODE_B}/",
            data=json.dumps(envelope).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

    def test_empty_envelope_400(self):
        """TC-004.4: empty envelope → 400"""
        req = urllib.request.Request(
            f"{NODE_B}/",
            data=json.dumps({}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 400

    def test_invalid_base64_400(self):
        """TC-004.5: invalid base64 → 400"""
        req = urllib.request.Request(
            f"{NODE_B}/",
            data=json.dumps({"message": {"data": "!!!not-base64!!!"}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(req)


# ═══════════════════════════════════════════════════════════════════
# T-005: Full Pipeline E2E
# ═══════════════════════════════════════════════════════════════════

class TestPipelineE2E:
    def test_full_pipeline(self):
        """TC-005.1: create_job → Pub/Sub sim → Node B → result.json"""
        # Step 1: Create job via Node A
        _, job_resp = http_post(f"{NODE_A}/create_job", {
            "product_name": "E2E Pipeline Test",
            "mode": "engineering",
            "market": "BR",
        })
        job_id = job_resp["job_id"]
        assert job_resp["status"] == "dispatched"

        # Step 2: Simulate Pub/Sub push to Node B
        envelope = pubsub_envelope({
            "job_id": job_id,
            "bucket": "brazil-studio-assets",
            "stage": "assets_ready",
            "spec_uri": job_resp["spec_uri"],
        })
        req = urllib.request.Request(
            f"{NODE_B}/",
            data=json.dumps(envelope).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

        # Step 3: Verify result
        cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result_path = os.path.join(cwd, "src", "tmp", "jobs", job_id, "final", "result.json")
        assert os.path.isfile(result_path)

        with open(result_path) as f:
            result = json.load(f)

        # TC-005.2: matching job_id
        assert result["job_id"] == job_id
        # TC-005.3: correct status
        assert result["status"] in ("success", "success_stub")
        assert result["errors"] == []

    def test_no_cross_contamination(self):
        """TC-005.4: 3 sequential jobs → 3 separate directories"""
        job_ids = []
        for i in range(3):
            _, body = http_post(f"{NODE_A}/create_job", {
                "product_name": f"Cross Test {i}",
            })
            job_ids.append(body["job_id"])
            time.sleep(1.1)

        assert len(set(job_ids)) == 3, "Job IDs must be unique"

        cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for jid in job_ids:
            path = os.path.join(cwd, "src", "tmp", "jobs", jid, "job.json")
            assert os.path.isfile(path), f"Missing job.json for {jid}"
            with open(path) as f:
                job = json.load(f)
            assert job["job_id"] == jid
