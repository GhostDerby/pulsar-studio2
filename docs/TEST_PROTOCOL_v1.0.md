# PULSAR STUDIO — Комплексний Протокол Тестування v1.0

> **Дата:** 2026-03-02
> **Статус:** Активний
> **Пріоритетність:** 🔴 Критичний → 🟠 Високий → 🟡 Середній → 🟢 Низький → ⚪ Інформаційний

---

## Зміст

1. [Проведені тестування](#1-проведені-тестування-baseline)
2. [P0 — Критичний](#2-p0--критичний-блокує-запуск)
3. [P1 — Високий](#3-p1--високий-основна-функціональність)
4. [P2 — Середній](#4-p2--середній-якість-та-стабільність)
5. [P3 — Низький](#5-p3--низький-оптимізація)
6. [P4 — Інформаційний](#6-p4--інформаційний-документація--метрики)
7. [Матриця покриття](#7-матриця-покриття)

---

## 1. Проведені тестування (Baseline)

### ✅ Smoke Test V1.0 — Local Mock Mode (завершено 2026-03-02)

| Перевірка | Результат | Деталі |
|-----------|-----------|--------|
| Node A запуск | ✅ Pass | Flask `:8080`, `LOCAL_MOCK=True` |
| Node B запуск | ✅ Pass | Flask `:8081`, `LOCAL_MOCK=True` |
| Node A `/health` | ✅ Pass | JSON відповідь з конфігурацією |
| Node B `/health` | ✅ Pass | JSON відповідь з mock-статусом |
| Node A `/create_job` | ✅ Pass | `job_1772430365` + `job_1772431687` |
| `job.json` на диску | ✅ Pass | 3 сцени, pricing, render_spec |
| Pub/Sub симуляція → Node B | ✅ Pass | base64 envelope → `success_stub` |
| Node B `result.json` | ✅ Pass | Pipeline acknowledged |

**Підтверджені компоненти (10):**
Flask routing, PricingEngine, Contracts (dataclasses), Job persistence, Pub/Sub envelope parsing, Stage routing, Graceful fallback (no media), Result generation, Module imports, Multi-port coexistence.

**Не покрито smoke тестом:**
GCS реальний запис/читання, Pub/Sub реальна публікація, Node C (SDXL/GPU), FFmpeg конвеєр, Watermark модуль, Docker-білди, Error handling під навантаженням.

---

## 2. P0 — 🔴 Критичний (блокує запуск)

### T-001. Unit Tests: PricingEngine

| | |
|--|--|
| **Пріоритет** | 🔴 P0 |
| **Компонент** | `src/shared/pricing_engine.py` |
| **Мета** | Переконатись, що ціноутворення коректне для всіх режимів |

**Тест-кейси:**

```
TC-001.1  mode="engineering", 3 scenes, margin=0.50 → gpu_scenes=0, cpu_scenes=3
TC-001.2  mode="hollywood",  3 scenes, margin=0.60 → gpu_scenes=3, cpu_scenes=0
TC-001.3  mode="mixed",      5 scenes, margin=0.50 → gpu_scenes=2, cpu_scenes=3
TC-001.4  margin=0.99 → price ≠ infinity (capped)
TC-001.5  margin=1.0  → price ≠ division by zero
TC-001.6  num_scenes=0 → graceful result, no crash
TC-001.7  num_scenes=100 → performance OK, correct totals
TC-001.8  Verify: suggested_price > total_cogs (always)
TC-001.9  Verify: CostBreakdown fields all >= 0
```

**Команда:**
```bash
cd /home/fstudiocore/pulsar-studio
PYTHONPATH=src python3 -m pytest tests/test_pricing_engine.py -v
```

---

### T-002. Unit Tests: Contracts (Dataclasses)

| | |
|--|--|
| **Пріоритет** | 🔴 P0 |
| **Компонент** | `src/shared/contracts.py` |
| **Мета** | Серіалізація/десеріалізація JobSpec коректна |

**Тест-кейси:**

```
TC-002.1  JobSpec.to_dict() → JSON-serializable dict
TC-002.2  Roundtrip: JobSpec → to_dict → JSON → dict → verify all fields
TC-002.3  SceneSpec defaults: motion="zoom_in"
TC-002.4  PricingSpec defaults: currency="USD", margin=0.5
TC-002.5  RenderSpec defaults: 1080×1920, 30fps, 3s
TC-002.6  JobResult.to_dict() with errors list
```

**Команда:**
```bash
PYTHONPATH=src python3 -m pytest tests/test_contracts.py -v
```

---

### T-003. Integration: Node A `/create_job` — End-to-End (Mock)

| | |
|--|--|
| **Пріоритет** | 🔴 P0 |
| **Компонент** | `src/node_a/budget_constructor.py` |
| **Мета** | HTTP POST → job.json на диску, правильна структура |

**Тест-кейси:**

```
TC-003.1  POST з product_name → status=dispatched, job_id starts with "job_"
TC-003.2  POST без body → defaults: product_name="Unknown Product", mode="engineering"
TC-003.3  mode="hollywood" → price > mode="engineering" price
TC-003.4  job.json file exists on disk at spec_uri path
TC-003.5  job.json contains all required fields (job_id, scenes, pricing, render_spec)
TC-003.6  /health → 200, contains local_mock=true
TC-003.7  GET /create_job → 405 Method Not Allowed
TC-003.8  Concurrent 10 POST requests → all return unique job_ids
```

**Команда:**
```bash
# Потребує запущений Node A:
LOCAL_MOCK=1 PYTHONPATH=src python3 -m node_a.budget_constructor &
sleep 2
PYTHONPATH=src python3 -m pytest tests/test_node_a_integration.py -v
```

---

### T-004. Integration: Node B Pub/Sub Envelope → Assembly Logic (Mock)

| | |
|--|--|
| **Пріоритет** | 🔴 P0 |
| **Компонент** | `src/node_b/cloud_run_assembly.py` |
| **Мета** | Pub/Sub envelope parsing + stage routing працює коректно |

**Тест-кейси:**

```
TC-004.1  stage="assets_ready" → triggers assembly logic → result.json created
TC-004.2  stage="job_created" → skips assembly, returns OK (200)
TC-004.3  stage="unknown_stage" → skips assembly, returns OK (200)
TC-004.4  Empty envelope → 400 Bad Request
TC-004.5  Invalid base64 data → 400 Bad Request
TC-004.6  No media assets → success_stub result with message
TC-004.7  result.json has correct structure: job_id, status, errors[]
TC-004.8  /health → 200
```

**Команда:**
```bash
LOCAL_MOCK=1 PORT=8081 PYTHONPATH=src python3 -m node_b.cloud_run_assembly &
sleep 2
PYTHONPATH=src python3 -m pytest tests/test_node_b_integration.py -v
```

---

### T-005. Full Pipeline: Node A → Node B (Mock, E2E)

| | |
|--|--|
| **Пріоритет** | 🔴 P0 |
| **Компонент** | Весь pipeline |
| **Мета** | Перевірка повного ланцюга від створення job до result |

**Тест-кейси:**

```
TC-005.1  POST /create_job → extract job_id → simulate Pub/Sub → Node B → result.json
TC-005.2  Verify job.json and result.json have matching job_id
TC-005.3  Verify result.json status is "success_stub" (no media) or "success"
TC-005.4  3 sequential jobs → 3 separate directories, no cross-contamination
TC-005.5  Pipeline with mode="hollywood" → correct pricing in both job.json and result
```

**Команда:**
```bash
# Запустити обидва ноди перед тестом:
LOCAL_MOCK=1 PYTHONPATH=src python3 -m node_a.budget_constructor &
LOCAL_MOCK=1 PORT=8081 PYTHONPATH=src python3 -m node_b.cloud_run_assembly &
sleep 3
PYTHONPATH=src python3 -m pytest tests/test_pipeline_e2e.py -v
```

---

## 3. P1 — 🟠 Високий (основна функціональність)

### T-006. GCS Integration: Node A Real Write

| | |
|--|--|
| **Пріоритет** | 🟠 P1 |
| **Компонент** | `src/node_a/budget_constructor.py` (real mode) |
| **Передумови** | GCP project `brazil-studio-v2`, bucket `brazil-studio-assets`, ADC configured |

**Тест-кейси:**

```
TC-006.1  LOCAL_MOCK=0 → upload_json_to_gcs creates blob in bucket
TC-006.2  Blob content matches job.json structure
TC-006.3  publish_job_message sends to pulsar-jobs topic
TC-006.4  Permission denied → graceful error (not 500 crash)
TC-006.5  Invalid bucket name → meaningful error message
```

**Команда:**
```bash
# Потребує реальних GCP credentials:
PYTHONPATH=src python3 -m pytest tests/test_gcs_integration.py -v
```

---

### T-007. GCS Integration: Node B Real Read + Assembly

| | |
|--|--|
| **Пріоритет** | 🟠 P1 |
| **Компонент** | `src/node_b/cloud_run_assembly.py` (real mode) |
| **Передумови** | GCS bucket з test media files |

**Тест-кейси:**

```
TC-007.1  Download frames from GCS → correct local paths
TC-007.2  Download scenes (MP4) from GCS → correct local paths
TC-007.3  Audio blob detection: music.mp3 found
TC-007.4  Audio blob detection: no audio → music_path=None
TC-007.5  Upload result.json to GCS after assembly
TC-007.6  Upload video.mp4 to GCS with correct content_type
```

---

### T-008. FFmpeg Assembly: Frames → Video

| | |
|--|--|
| **Пріоритет** | 🟠 P1 |
| **Компонент** | `ffmpeg_frames_to_pseudomotion()` |
| **Передумови** | `ffmpeg` installed, test PNG frames |

**Тест-кейси:**

```
TC-008.1  3 PNG frames → 9s video (3s each), 1080×1920
TC-008.2  Output codec = H.264, pixel format = yuv420p
TC-008.3  Zoompan effect applied (visual check or metadata)
TC-008.4  With music.mp3 → audio track present, volume=0.6
TC-008.5  Without music → no audio track
TC-008.6  1 frame → 3s video, no crash
TC-008.7  Empty frame list → RuntimeError raised
```

**Команда:**
```bash
# Потребує ffmpeg + test media:
PYTHONPATH=src python3 -m pytest tests/test_ffmpeg_assembly.py -v
```

---

### T-009. FFmpeg Assembly: Scenes Concatenation

| | |
|--|--|
| **Пріоритет** | 🟠 P1 |
| **Компонент** | `ffmpeg_concat_scenes()` |
| **Передумови** | `ffmpeg` installed, test MP4 clips |

**Тест-кейси:**

```
TC-009.1  3 MP4 clips → concatenated output, correct duration
TC-009.2  Output resolution forced to 1080×1920
TC-009.3  With music → audio mixed, -shortest applied
TC-009.4  Concat list file created and cleaned properly
TC-009.5  1 clip → output = copy of clip (no crash)
```

---

### T-010. Watermark Module

| | |
|--|--|
| **Пріоритет** | 🟠 P1 |
| **Компонент** | `ffmpeg_concat_scenes()` watermark logic |
| **Передумови** | `ffmpeg`, fonts-dejavu-core, test PNG watermark |

**Тест-кейси:**

```
TC-010.1  WATERMARK_ENABLED=1, no PNG → drawtext fallback applied
TC-010.2  WATERMARK_ENABLED=1, PNG GCS URI → overlay applied
TC-010.3  WATERMARK_ENABLED=0 → clean video, no watermark
TC-010.4  opacity=0.25 → watermark semi-transparent
TC-010.5  position=bottom → safe margin 300px from bottom
TC-010.6  position=top → safe margin 200px from top
TC-010.7  position=center → vertically centered
TC-010.8  WATERMARK_SAFE_MARGIN=0 → default positions (20px, 40px)
TC-010.9  Special chars in WATERMARK_TEXT (colons, quotes) → escaped correctly
```

---

### T-011. Node C: SDXL Worker Health & Predict (GPU Required)

| | |
|--|--|
| **Пріоритет** | 🟠 P1 |
| **Компонент** | `src/node_c/sdxl_worker.py` |
| **Передумови** | NVIDIA GPU, CUDA, SDXL model downloaded, GCS bucket |

**Тест-кейси:**

```
TC-011.1  /health before model load → {"status":"loading"}, 503
TC-011.2  /health after model load → {"status":"ready"}, 200
TC-011.3  /predict with prompt → generates PNG, uploads to GCS
TC-011.4  /predict response has image_uri in gs:// format
TC-011.5  rembg removes background (output has transparency)
TC-011.6  /predict without prompt → defaults to "Product"
TC-011.7  /predict large batch (5 sequential) → stable, no OOM
TC-011.8  CUDA not available → model stays on CPU (slow but no crash)
```

**Команда:**
```bash
# Потребує GPU + SDXL model:
BUCKET_NAME=brazil-studio-assets PYTHONPATH=src python3 -m pytest tests/test_node_c_gpu.py -v
```

---

## 4. P2 — 🟡 Середній (якість та стабільність)

### T-012. Error Handling & Edge Cases

| | |
|--|--|
| **Пріоритет** | 🟡 P2 |
| **Компонент** | Всі ноди |
| **Мета** | Система не крашиться на невалідних даних |

**Тест-кейси:**

```
TC-012.1  Node A: POST з невалідним JSON → 400, не 500
TC-012.2  Node A: POST з порожнім body → defaults працюють
TC-012.3  Node B: Pub/Sub без "message" ключа → 400
TC-012.4  Node B: Pub/Sub з пустим "data" → 400
TC-012.5  Node B: Assembly exception → result.json status="failed", errors filled
TC-012.6  Node C: /predict без "instances" → error message
TC-012.7  Node C: /predict з порожнім prompt → defaults працюють
TC-012.8  All nodes: OPTIONS/PUT/DELETE → 405
TC-012.9  All nodes: very large payload (>1MB) → handled or rejected gracefully
```

---

### T-013. Docker Build & Container Tests

| | |
|--|--|
| **Пріоритет** | 🟡 P2 |
| **Компонент** | Всі Dockerfiles |
| **Мета** | Контейнери будуються і запускаються коректно |

**Тест-кейси:**

```
TC-013.1  docker build node_a → success, image < 500MB
TC-013.2  docker build node_b → success, ffmpeg available inside
TC-013.3  docker build node_c → success, torch import OK
TC-013.4  docker run node_a → /health returns 200
TC-013.5  docker run node_b → /health returns 200, ffmpeg -version OK
TC-013.6  docker run node_c → /health returns 503 (loading, no GPU)
TC-013.7  PYTHONPATH set correctly → shared/ imports work
TC-013.8  gunicorn starts with correct workers/threads config
```

**Команда:**
```bash
# Node A:
docker build -t pulsar-node-a -f src/node_a/Dockerfile .
docker run -e PORT=8080 -p 8080:8080 pulsar-node-a &
curl http://localhost:8080/health

# Node B:
docker build -t pulsar-node-b -f src/node_b/Dockerfile .
docker run -e PORT=8081 -p 8081:8081 pulsar-node-b &
curl http://localhost:8081/health
docker exec $(docker ps -q -f ancestor=pulsar-node-b) ffmpeg -version
```

---

### T-014. Concurrent Requests & Stability

| | |
|--|--|
| **Пріоритет** | 🟡 P2 |
| **Компонент** | Node A, Node B |
| **Мета** | Стабільність під навантаженням |

**Тест-кейси:**

```
TC-014.1  10 concurrent /create_job → all 200, unique job_ids
TC-014.2  50 sequential /create_job → no memory leak, stable response time
TC-014.3  10 concurrent Pub/Sub pushes to Node B → all 200, unique results
TC-014.4  Node A under load → /health still responds < 100ms
TC-014.5  Job ID uniqueness guarantee across 100 rapid requests
```

**Команда:**
```bash
# Apache Bench або wrk:
ab -n 50 -c 10 -p /tmp/job_payload.json -T application/json http://localhost:8080/create_job
```

---

### T-015. tools/publish_stage.py

| | |
|--|--|
| **Пріоритет** | 🟡 P2 |
| **Компонент** | `tools/publish_stage.py` |
| **Передумови** | GCP Pub/Sub configured |

**Тест-кейси:**

```
TC-015.1  python tools/publish_stage.py job_123 assets_ready → Published
TC-015.2  Missing args → Usage message, exit code 1
TC-015.3  Invalid project → meaningful error
TC-015.4  Message format matches Node B expected envelope
```

---

## 5. P3 — 🟢 Низький (оптимізація)

### T-016. Performance Benchmarks

| | |
|--|--|
| **Пріоритет** | 🟢 P3 |
| **Компонент** | Весь pipeline |

**Тест-кейси:**

```
TC-016.1  Node A /create_job average latency < 50ms (mock mode)
TC-016.2  Node A /create_job average latency < 2s (GCS mode)
TC-016.3  Node B assembly (3 frames, no music) < 30s
TC-016.4  Node B assembly (3 scenes, music, watermark) < 60s
TC-016.5  Node C SDXL inference (1 image) < 30s (A100)
TC-016.6  Full pipeline E2E (create → generate → assemble) < 120s
TC-016.7  Memory usage per node < 512MB (A/B), < 16GB (C/GPU)
```

---

### T-017. Pricing Engine Accuracy

| | |
|--|--|
| **Пріоритет** | 🟢 P3 |
| **Компонент** | `PricingEngine` |

**Тест-кейси:**

```
TC-017.1  Monte Carlo: 1000 random (mode, scenes, margin) → all prices valid
TC-017.2  Verify cost constants against real GCP invoices
TC-017.3  Hollywood 10 scenes vs Engineering 10 scenes → cost ratio ≈ 5-10×
TC-017.4  Marginal cost per additional scene is consistent
TC-017.5  Currency field propagates through entire pipeline
```

---

### T-018. Local Mock Parity

| | |
|--|--|
| **Пріоритет** | 🟢 P3 |
| **Компонент** | LOCAL_MOCK mode |

**Тест-кейси:**

```
TC-018.1  Mock job.json identical structure to GCS job.json
TC-018.2  Mock result.json identical structure to GCS result.json
TC-018.3  Health endpoint shows local_mock=true/false correctly
TC-018.4  LOCAL_MOCK=0 → google.cloud imports execute
TC-018.5  LOCAL_MOCK=1 → google.cloud NOT imported
```

---

## 6. P4 — ⚪ Інформаційний (документація / метрики)

### T-019. Code Quality & Linting

```
TC-019.1  flake8 src/ → 0 errors
TC-019.2  mypy src/ --ignore-missing-imports → 0 errors
TC-019.3  All functions have docstrings
TC-019.4  No hardcoded secrets in source code
TC-019.5  .gitignore covers tmp/, __pycache__/, *.pyc
```

### T-020. Documentation Verification

```
TC-020.1  SYSTEM_OVERVIEW.md matches current architecture
TC-020.2  RUNTIME_FLOW.md matches current code flow
TC-020.3  README.md has setup instructions
TC-020.4  All ENV variables documented
TC-020.5  Dockerfile comments match actual behavior
```

---

## 7. Матриця покриття

| Компонент | P0 | P1 | P2 | P3 | Smoke ✅ |
|-----------|----|----|----|----|----------|
| **PricingEngine** | T-001 | — | — | T-017 | Частково |
| **Contracts** | T-002 | — | — | — | Частково |
| **Node A (budget)** | T-003 | T-006 | T-012, T-014 | T-016 | ✅ |
| **Node B (assembly)** | T-004 | T-007, T-008, T-009, T-010 | T-012, T-014 | T-016 | ✅ |
| **Node C (SDXL/GPU)** | — | T-011 | T-012 | T-016 | ❌ |
| **Pipeline E2E** | T-005 | — | — | T-016 | ✅ Mock |
| **Docker** | — | — | T-013 | — | ❌ |
| **tools/** | — | — | T-015 | — | ❌ |
| **Mock parity** | — | — | — | T-018 | — |
| **Code quality** | — | — | — | — | ❌ |

### Підсумок

| Пріоритет | Тестів | Тест-кейсів | Статус |
|-----------|--------|-------------|--------|
| 🔴 P0 Критичний | 5 | 32 | ⏳ Smoke done, unit/integration — потрібно |
| 🟠 P1 Високий | 6 | 41 | ❌ Потребує GCP / GPU / ffmpeg media |
| 🟡 P2 Середній | 4 | 27 | ❌ Потребує Docker + load testing |
| 🟢 P3 Низький | 3 | 17 | ❌ Оптимізаційні |
| ⚪ P4 Інфо | 2 | 10 | ❌ Документація |
| **Всього** | **20** | **127** | — |

---

## Наступні кроки (рекомендація)

1. **Зараз:** Реалізувати T-001, T-002 (unit tests PricingEngine + Contracts) — ніяких залежностей
2. **Далі:** T-003, T-004 (integration tests з Flask test client) — mock mode
3. **Далі:** T-005 (E2E pipeline test) — автоматизувати те, що вже зроблено вручну
4. **Коли GCP готовий:** T-006, T-007 (GCS integration)
5. **Коли GPU доступний:** T-011 (Node C SDXL)
6. **Перед продакшн:** T-013 (Docker), T-014 (load), T-010 (watermark)
