"""
T-012: Error Handling & Edge Cases
T-013: Dockerfile Validation (static checks)
T-014: Concurrent Requests & Stability
Priority: P2 Medium
"""
import json
import os
import sys
import time
import base64
import urllib.request
import urllib.error
import concurrent.futures
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

NODE_A = "http://localhost:8080"
NODE_B = "http://localhost:8081"

DOCKERFILES = {
    "node_a": os.path.join(os.path.dirname(__file__), "..", "src", "node_a", "Dockerfile"),
    "node_b": os.path.join(os.path.dirname(__file__), "..", "src", "node_b", "Dockerfile"),
    "node_c": os.path.join(os.path.dirname(__file__), "..", "src", "node_c", "Dockerfile"),
}


def http_post(url, data=None, expect_error=False):
    body = json.dumps(data or {}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if expect_error:
            return e.code, None
        raise


def http_method(method, url):
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def pubsub_envelope(payload: dict) -> dict:
    data_b64 = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    return {"message": {"data": data_b64}}


# ═══════════════════════════════════════════════════════════════════
# T-012: Error Handling & Edge Cases
# ═══════════════════════════════════════════════════════════════════

class TestNodeAErrorHandling:
    def test_empty_body_uses_defaults(self):
        """TC-012.2: POST with empty body → defaults work, no crash"""
        status, body = http_post(f"{NODE_A}/create_job", {})
        assert status == 200
        assert body["status"] == "dispatched"
        # default product name should be set
        spec_path = body["spec_uri"].replace("file://", "")
        with open(spec_path) as f:
            job = json.load(f)
        assert job["product_name"] == "Unknown Product"
        assert job["mode"] == "engineering"
        assert job["market"] == "BR"

    def test_extra_fields_ignored(self):
        """Node A ignores unknown fields gracefully"""
        status, body = http_post(f"{NODE_A}/create_job", {
            "product_name": "Widget",
            "unknown_field": "should be ignored",
            "extra": 42,
        })
        assert status == 200
        assert body["status"] == "dispatched"

    def test_unicode_product_name(self):
        """Unicode in product_name handled correctly"""
        status, body = http_post(f"{NODE_A}/create_job", {
            "product_name": "Продукт 日本語 🎵",
        })
        assert status == 200
        spec_path = body["spec_uri"].replace("file://", "")
        with open(spec_path) as f:
            job = json.load(f)
        assert job["product_name"] == "Продукт 日本語 🎵"

    def test_very_long_product_name(self):
        """Very long product name doesn't crash"""
        long_name = "X" * 5000
        status, body = http_post(f"{NODE_A}/create_job", {"product_name": long_name})
        assert status == 200

    def test_numeric_mode(self):
        """Numeric mode string → treated as unknown mode (mixed)"""
        status, body = http_post(f"{NODE_A}/create_job", {"mode": 123})
        assert status == 200


class TestNodeBErrorHandling:
    def test_empty_envelope_400(self):
        """TC-012.3: Pub/Sub without 'message' → 400"""
        status, _ = http_post(f"{NODE_B}/", {}, expect_error=True)
        assert status == 400

    def test_empty_data_400(self):
        """TC-012.4: Pub/Sub with empty data → 400"""
        status, _ = http_post(f"{NODE_B}/", {"message": {}}, expect_error=True)
        assert status == 400

    def test_malformed_json_in_data(self):
        """Invalid JSON inside base64 data"""
        bad_data = base64.b64encode(b"not json!!!").decode()
        req = urllib.request.Request(
            f"{NODE_B}/",
            data=json.dumps({"message": {"data": bad_data}}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                # Should either 400 or 500
                pass
        except urllib.error.HTTPError as e:
            assert e.code in (400, 500)

    def test_missing_job_id_in_payload(self):
        """Payload without job_id → 400 (validated)"""
        envelope = pubsub_envelope({"stage": "assets_ready"})
        status, _ = http_post(f"{NODE_B}/", envelope, expect_error=True)
        assert status == 400


class TestHTTPMethods:
    def test_node_a_get_create_job_405(self):
        """TC-012.8: GET /create_job → 405"""
        status = http_method("GET", f"{NODE_A}/create_job")
        assert status == 405

    def test_node_a_put_create_job_405(self):
        """PUT /create_job → 405"""
        status = http_method("PUT", f"{NODE_A}/create_job")
        assert status == 405

    def test_node_a_delete_create_job_405(self):
        """DELETE /create_job → 405"""
        status = http_method("DELETE", f"{NODE_A}/create_job")
        assert status == 405

    def test_node_a_nonexistent_route_404(self):
        """Node A: /nonexistent → 404"""
        status = http_method("GET", f"{NODE_A}/nonexistent")
        assert status == 404

    def test_node_b_nonexistent_route_404(self):
        """Node B: /nonexistent → 404"""
        status = http_method("GET", f"{NODE_B}/nonexistent")
        assert status == 404


# ═══════════════════════════════════════════════════════════════════
# T-013: Dockerfile Validation (static analysis)
# ═══════════════════════════════════════════════════════════════════

class TestDockerfileValidation:
    @pytest.mark.parametrize("node", ["node_a", "node_b", "node_c"])
    def test_dockerfile_exists(self, node):
        """TC-013: Dockerfile exists for each node"""
        path = DOCKERFILES[node]
        assert os.path.isfile(path), f"Missing Dockerfile: {path}"

    @pytest.mark.parametrize("node", ["node_a", "node_b", "node_c"])
    def test_dockerfile_has_from(self, node):
        """Dockerfile starts with FROM"""
        with open(DOCKERFILES[node]) as f:
            content = f.read()
        assert content.strip().startswith("FROM"), "Dockerfile must start with FROM"

    @pytest.mark.parametrize("node", ["node_a", "node_b", "node_c"])
    def test_dockerfile_has_python_base(self, node):
        """Dockerfile uses python base image"""
        with open(DOCKERFILES[node]) as f:
            content = f.read()
        assert "python:" in content.lower() or "python3" in content.lower()

    @pytest.mark.parametrize("node", ["node_a", "node_b", "node_c"])
    def test_dockerfile_sets_pythonpath(self, node):
        """PYTHONPATH is configured for shared/ imports"""
        with open(DOCKERFILES[node]) as f:
            content = f.read()
        assert "PYTHONPATH" in content

    @pytest.mark.parametrize("node", ["node_a", "node_b", "node_c"])
    def test_dockerfile_copies_shared(self, node):
        """shared/ directory is copied into container"""
        with open(DOCKERFILES[node]) as f:
            content = f.read()
        assert "shared/" in content

    @pytest.mark.parametrize("node", ["node_a", "node_b", "node_c"])
    def test_dockerfile_has_cmd_or_entrypoint(self, node):
        """Dockerfile has CMD or ENTRYPOINT"""
        with open(DOCKERFILES[node]) as f:
            content = f.read()
        assert "CMD" in content or "ENTRYPOINT" in content

    @pytest.mark.parametrize("node", ["node_a", "node_b", "node_c"])
    def test_dockerfile_installs_requirements(self, node):
        """requirements.txt is installed"""
        with open(DOCKERFILES[node]) as f:
            content = f.read()
        assert "requirements.txt" in content
        assert "pip install" in content

    def test_node_b_has_ffmpeg(self):
        """TC-013.2: Node B Dockerfile installs ffmpeg"""
        with open(DOCKERFILES["node_b"]) as f:
            content = f.read()
        assert "ffmpeg" in content

    def test_node_b_has_fonts(self):
        """Node B Dockerfile installs fonts for watermark"""
        with open(DOCKERFILES["node_b"]) as f:
            content = f.read()
        assert "fonts-dejavu" in content

    @pytest.mark.parametrize("node", ["node_a", "node_b", "node_c"])
    def test_requirements_exist(self, node):
        """requirements.txt exists for each node"""
        req_path = os.path.join(os.path.dirname(DOCKERFILES[node]), "requirements.txt")
        assert os.path.isfile(req_path)

    @pytest.mark.parametrize("node", ["node_a", "node_b", "node_c"])
    def test_requirements_has_flask(self, node):
        """Flask is in requirements"""
        req_path = os.path.join(os.path.dirname(DOCKERFILES[node]), "requirements.txt")
        with open(req_path) as f:
            content = f.read().lower()
        assert "flask" in content

    @pytest.mark.parametrize("node", ["node_a", "node_b", "node_c"])
    def test_gunicorn_in_cmd(self, node):
        """TC-013.8: gunicorn used in CMD"""
        with open(DOCKERFILES[node]) as f:
            content = f.read()
        assert "gunicorn" in content


# ═══════════════════════════════════════════════════════════════════
# T-014: Concurrent Requests & Stability
# ═══════════════════════════════════════════════════════════════════

class TestConcurrency:
    def test_concurrent_create_jobs(self):
        """TC-014.1: 10 concurrent /create_job → all 200, unique job_ids"""
        def create_job(i):
            return http_post(f"{NODE_A}/create_job", {
                "product_name": f"Concurrent Test {i}",
            })

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(create_job, i) for i in range(10)]
            results = [f.result() for f in futures]

        statuses = [r[0] for r in results]
        ids = [r[1]["job_id"] for r in results]

        assert all(s == 200 for s in statuses), f"Some requests failed: {statuses}"
        assert len(set(ids)) == 10, f"Duplicate job IDs: {ids}"

    def test_sequential_stability(self):
        """TC-014.2: 20 sequential requests → stable response"""
        times = []
        for i in range(20):
            t0 = time.time()
            status, body = http_post(f"{NODE_A}/create_job", {"product_name": f"Seq {i}"})
            elapsed = time.time() - t0
            times.append(elapsed)
            assert status == 200
            time.sleep(0.05)

        avg = sum(times) / len(times)
        # Average should be under 500ms for local mock
        assert avg < 0.5, f"Average response time too high: {avg:.3f}s"

    def test_concurrent_pubsub_to_node_b(self):
        """TC-014.3: 5 concurrent Pub/Sub pushes → all 200"""
        def push_message(i):
            envelope = pubsub_envelope({
                "job_id": f"concurrent_b_{i}_{int(time.time())}",
                "stage": "job_created",  # skipped stage, fast
            })
            req = urllib.request.Request(
                f"{NODE_B}/",
                data=json.dumps(envelope).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                return resp.status

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(push_message, i) for i in range(5)]
            statuses = [f.result() for f in futures]

        assert all(s == 200 for s in statuses)

    def test_health_under_load(self):
        """TC-014.4: /health responds fast even during other work"""
        # Fire 5 job creations in background
        def bg_create():
            http_post(f"{NODE_A}/create_job", {"product_name": "BG"})

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        for _ in range(5):
            pool.submit(bg_create)

        # Health should still be fast
        t0 = time.time()
        req = urllib.request.Request(f"{NODE_A}/health")
        with urllib.request.urlopen(req) as resp:
            elapsed = time.time() - t0
            assert resp.status == 200
            assert elapsed < 0.5

        pool.shutdown(wait=True)
