# Невиконані завдання аудиту

## 🚫 BLOCKER
- [ ] **B-01** GCP Project створити + billing
- [ ] **B-03** Node C (GPU) — error handling, LOCAL_MOCK mode, тестування
- [ ] **B-04** API Gateway / Auth для `/create_job`
- [ ] **B-05** AI scene planning замість hardcoded 3 сцен (Gemini API)

## 🔴 CRITICAL
- [ ] **C-01** CI/CD Pipeline (GitHub Actions + Cloud Build)
- [ ] **C-02** Secrets Management (.env + Secret Manager)
- [ ] **C-03** Error Recovery (retry, DLQ, circuit breaker)
- [ ] **C-06** Node B → Node C HTTP integration (pipeline з'єднання)
- [ ] **C-07** Pub/Sub Subscription → Node B (push endpoint)
- [ ] **C-08** Watermark — PNG overlay з GCS (інтеграція `download_watermark_from_gcs`)

## 🟠 HIGH
- [ ] **H-01** Monitoring & Alerting (Cloud Monitoring, structured logging)
- [ ] **H-02** Input Validation (pydantic schemas)
- [ ] **H-03** Database / Job Tracking (Firestore або Cloud SQL)
- [ ] **H-04** Pricing калібрація (реальні GCP invoices)
- [ ] **H-05** Health Check для залежностей (GCS, Pub/Sub, GPU, ffmpeg)
- [ ] **H-06** Gunicorn Workers > 1 для production
- [ ] **H-07** FFmpeg subprocess security (sanitize paths)
- [ ] **H-08** Delivery endpoint (CDN link, webhook notification)
- [ ] **H-09** Idempotency (deduplication key)

## 🟡 MEDIUM
- [ ] **M-01** Multi-region / CDN для відео
- [ ] **M-02** gpu_worker/ заповнити (порожній README)
- [ ] **M-03** Docs заповнити (PULSAR_STUDIO_CORE_v1.0.md = 0 bytes)
- [ ] **M-04** API versioning (`/v1/create_job`)
- [ ] **M-05** Structured JSON logging
- [ ] **M-06** Graceful shutdown

## ✅ ВИКОНАНО
- [x] **B-02** Docker Compose (docker-compose.yml + gpu overlay)
- [x] **C-04** Docker Compose для локальної розробки
- [x] **C-05** .gitignore оновлений
- [x] **5.1** .env.example створено
- [x] **5.4** Hardcoded project ID замінено на ENV
- [x] **5.5** python-dotenv додано
- [x] **2.2** GCS init скрипт створено
