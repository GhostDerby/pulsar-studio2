# RUNTIME FLOW
1. Seller submits product data
2. Image generated or provided
3. Motion layer applied (optional GPU)
4. Assembly via FFmpeg
5. Watermark applied (if unpaid)
6. Final video stored in GCS
7. Delivery link sent
Fallback:
If GPU fails → pseudo-motion.
