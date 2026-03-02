# Завдання для власника проекту (Manual / Console)

> Ці завдання потребують доступу до GCP Console, billing, або фізичного обладнання.
> Агент НЕ може їх виконати.

---

## Фаза 1: Інфраструктура (пріоритет 🔴)

### GCP Project
- [ ] Створити GCP project (рекомендований ID: `pulsar-studio-prod`)
- [ ] Прив'язати billing account
- [ ] Увімкнути APIs:
  - Cloud Run API
  - Cloud Storage API
  - Pub/Sub API
  - Container Registry API
  - Cloud Build API

### IAM & Service Account
- [ ] Створити Service Account: `pulsar-pipeline@<project-id>.iam.gserviceaccount.com`
- [ ] Додати ролі: Storage Admin, Pub/Sub Publisher, Cloud Run Invoker
- [ ] Завантажити JSON ключ → `~/.config/gcloud/pulsar-sa.json`
- [ ] Виконати: `gcloud auth activate-service-account --key-file=pulsar-sa.json`

### Cloud Storage
- [ ] Створити bucket: `pulsar-studio-assets` (region: `us-central1`)
- [ ] Після створення запустити: `BUCKET_NAME=pulsar-studio-assets python3 tools/init_gcs_structure.py`
- [ ] Завантажити watermark PNG: `gsutil cp watermark.png gs://pulsar-studio-assets/watermarks/default.png`

### Pub/Sub
- [ ] Створити topic: `pulsar-jobs`
- [ ] Створити push subscription на URL Node B (після deploy на Cloud Run)

---

## Фаза 2: Deploy (після Фази 1)

### Cloud Run
- [ ] Deploy Node A: `gcloud run deploy node-a --source=. --dockerfile=src/node_a/Dockerfile`
- [ ] Deploy Node B: `gcloud run deploy node-b --source=. --dockerfile=src/node_b/Dockerfile`
- [ ] Налаштувати ENV variables в Cloud Run для кожного сервісу
- [ ] Оновити Pub/Sub subscription URL на Node B Cloud Run URL

### GPU Worker (Node C)
- [ ] Обрати провайдер: RunPod / Vertex AI / GKE GPU Node
- [ ] Deploy Node C з GPU access
- [ ] Перевірити SDXL model download (перший старт ~5-10 хв)

---

## Фаза 3: Безпека (до публічного доступу)

- [ ] Створити API key для `/create_job`
- [ ] Налаштувати CORS policy
- [ ] Додати Secret Manager для credentials
- [ ] Перевірити що `.env` в `.gitignore`

---

## Скопіюй `.env.example` → `.env` і заповни:
```bash
cp .env.example .env
# Відредагуй .env з реальними значеннями:
# GOOGLE_CLOUD_PROJECT=pulsar-studio-prod
# BUCKET_NAME=pulsar-studio-assets
# GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/pulsar-sa.json
```
