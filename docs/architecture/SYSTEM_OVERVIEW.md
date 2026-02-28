# SYSTEM OVERVIEW
Version: 1.0 Stable

## Core Pipeline
Image → Motion → Assembly → Watermark → Delivery
Core is service-independent.
External providers:
- Vertex AI
- RunPod
- Local GPU
- CPU fallback
Core must remain stable.
Providers may change.

## Design Principles
- No vendor lock-in
- Economic justification required
- Revenue-first development
- Modular architecture
