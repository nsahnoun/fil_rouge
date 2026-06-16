# ================================================================
# CEPHALOMETRIC API — FastAPI
# ================================================================
# Endpoints :
#   POST /predict          → image → 29 landmarks JSON
#   GET  /health           → statut du serveur + modèle chargé
#
# Lancement :
#   uvicorn ceph_api:app --host 0.0.0.0 --port 8000 --reload
# ================================================================

import io
import os
import time
import logging
from contextlib import asynccontextmanager
from typing import List

import cv2
import numpy as np
import tensorflow as tf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────
# CONFIG — à adapter à votre environnement
# ─────────────────────────────────────────────────────────────────
MODEL_PATH       = os.getenv("MODEL_PATH", "best_hrnet_w64_800px.keras")
IMG_SIZE         = (800, 800)
HEATMAP_SIZE     = (IMG_SIZE[0] // 4, IMG_SIZE[1] // 4)   # (200, 200)
NUM_LANDMARKS    = 29
PIXEL_SPACING_MM = float(os.getenv("PIXEL_SPACING_MM", "0.1"))

TTA_SCALES       = [0.9, 1.0, 1.1]
TTA_ANGLES       = [-3, 0, 3]

# Noms anatomiques des 29 landmarks (clé = index sortie modèle 1‑29)

LANDMARK_NAMES = {
    1: "Incision_inf", 2: "Nasion", 3: "Orbitale", 4: "Porion", 5: "Subspinale (A)",
    6: "Supramentale (B)", 7: "Pogonion", 8: "Menton", 9: "Gnathion",
    10: "Gonion", 11: "Sella", 12: "Incision_sup", 13: "Upper_lip",
    14: "Lower_lip", 15: "Subnasale", 16: "Soft_tissue_pogonion",
    17: "Posterior_nasal_spine", 18: "Anterior_nasal_spine", 19: "Articulare",
    20: "Basion", 21: "Pterygomaxillare", 22: "Upper_1_root", 23: "Upper_1_tip",
    24: "Lower_1_root", 25: "Lower_1_tip", 26: "Lower_molar_mesial",
    27: "Upper_molar_mesial", 28: "Condylion", 29: "Centre de la Face",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ceph_api")

# ─────────────────────────────────────────────────────────────────
# ÉTAT GLOBAL — modèle chargé une seule fois au démarrage
# ─────────────────────────────────────────────────────────────────
class AppState:
    model = None
    load_time: float = 0.0
    model_path: str = ""

state = AppState()


# ─────────────────────────────────────────────────────────────────
# COUCHE CUSTOM (nécessaire pour load_model)
# ─────────────────────────────────────────────────────────────────
@tf.keras.utils.register_keras_serializable()
class DualAttention(tf.keras.layers.Layer):
    def __init__(self, filters, reduction=8, **kwargs):
        super().__init__(**kwargs)
        self.filters   = filters
        self.reduction = reduction
        self.fc1       = tf.keras.layers.Dense(filters // reduction, activation="relu")
        self.fc2       = tf.keras.layers.Dense(filters, activation="sigmoid")
        self.conv_s    = tf.keras.layers.Conv2D(1, 7, padding="same", activation="sigmoid")

    def call(self, x):
        avg_p = tf.reduce_mean(x, [1, 2])
        max_p = tf.reduce_max(x,  [1, 2])
        ca    = self.fc2(self.fc1(avg_p)) + self.fc2(self.fc1(max_p))
        x     = x * tf.reshape(ca, (-1, 1, 1, self.filters))
        sa    = self.conv_s(tf.concat([
            tf.reduce_mean(x, -1, keepdims=True),
            tf.reduce_max(x,  -1, keepdims=True),
        ], -1))
        return x * sa

    def get_config(self):
        cfg = super().get_config()
        cfg.update({"filters": self.filters, "reduction": self.reduction})
        return cfg


# ─────────────────────────────────────────────────────────────────
# UTILITIES (letterbox + DARK decoding + TTA)
# ─────────────────────────────────────────────────────────────────
def letterbox_resize(img: np.ndarray, target=IMG_SIZE):
    h, w   = img.shape[:2]
    th, tw = target
    scale  = min(tw / w, th / h)
    new_w  = int(round(w * scale))
    new_h  = int(round(h * scale))
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    if resized.dtype != np.float32:
        resized = resized.astype(np.float32) / 255.0
    pad_x = (tw - new_w) // 2
    pad_y = (th - new_h) // 2
    out   = np.zeros((th, tw), dtype=np.float32)
    out[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
    return out, scale, pad_x, pad_y


def inv_letterbox(pts: np.ndarray, scale: float, pad_x: int, pad_y: int) -> np.ndarray:
    out = pts.copy().astype(np.float32)
    out[:, 0] = (pts[:, 0] - pad_x) / scale
    out[:, 1] = (pts[:, 1] - pad_y) / scale
    return out


def dark_decode(heatmap: np.ndarray, blur_kernel: int = 11):
    H, W     = heatmap.shape
    peak_idx = np.argmax(heatmap)
    py, px   = np.unravel_index(peak_idx, (H, W))
    smoothed = cv2.GaussianBlur(heatmap, (blur_kernel, blur_kernel), 3.0)
    smoothed = np.maximum(smoothed, 1e-9)
    log_sm   = np.log(smoothed)
    px = int(np.clip(px, 1, W - 2))
    py = int(np.clip(py, 1, H - 2))
    dx  = (log_sm[py, px + 1] - log_sm[py, px - 1]) / 2.0
    dy  = (log_sm[py + 1, px] - log_sm[py - 1, px]) / 2.0
    dxx = log_sm[py, px + 1] + log_sm[py, px - 1] - 2 * log_sm[py, px]
    dyy = log_sm[py + 1, px] + log_sm[py - 1, px] - 2 * log_sm[py, px]
    dxy = (log_sm[py + 1, px + 1] - log_sm[py + 1, px - 1]
           - log_sm[py - 1, px + 1] + log_sm[py - 1, px - 1]) / 4.0
    det = dxx * dyy - dxy ** 2
    if abs(det) < 1e-8:
        return float(px), float(py)
    offset_x = np.clip(-(dyy * dx - dxy * dy) / det, -1.0, 1.0)
    offset_y = np.clip(-(dxx * dy - dxy * dx) / det, -1.0, 1.0)
    return float(px) + offset_x, float(py) + offset_y


def decode_heatmaps(heatmaps: np.ndarray) -> np.ndarray:
    heatmaps = np.clip(heatmaps, -15, 15)
    hm       = 1.0 / (1.0 + np.exp(-heatmaps))
    return np.array(
        [dark_decode(hm[:, :, c]) for c in range(hm.shape[-1])],
        dtype=np.float32,
    )


def heatmap_to_image_coords(coords_hm: np.ndarray) -> np.ndarray:
    coords = coords_hm.copy().astype(np.float32)
    coords[:, 0] *= IMG_SIZE[1] / HEATMAP_SIZE[1]
    coords[:, 1] *= IMG_SIZE[0] / HEATMAP_SIZE[0]
    return coords


def predict_tta(model, img_lb: np.ndarray, sc: float, px: int, py: int) -> np.ndarray:
    H, W   = img_lb.shape
    HH, HW = HEATMAP_SIZE
    accumulated_hm = None

    for s in TTA_SCALES:
        for a in TTA_ANGLES:
            M       = cv2.getRotationMatrix2D((W / 2, H / 2), a, s)
            img_tta = cv2.warpAffine(img_lb, M, (W, H),
                                     flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REFLECT_101)
            inp     = np.expand_dims(img_tta, (0, -1)).astype(np.float32)

            preds   = model.predict(inp, verbose=0)
            hm_raw  = preds[0][0] if isinstance(preds, list) else preds[0]

            Mi     = cv2.getRotationMatrix2D((HW / 2, HH / 2), -a, 1.0 / s)
            hm_inv = np.stack(
                [
                    cv2.warpAffine(hm_raw[:, :, c], Mi, (HW, HH),
                                   flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT,
                                   borderValue=0.0)
                    for c in range(hm_raw.shape[-1])
                ],
                axis=-1,
            )

            accumulated_hm = hm_inv if accumulated_hm is None else accumulated_hm + hm_inv

    accumulated_hm /= len(TTA_SCALES) * len(TTA_ANGLES)

    coords_hm   = decode_heatmaps(accumulated_hm)
    coords_lb   = heatmap_to_image_coords(coords_hm)
    coords_orig = inv_letterbox(coords_lb, sc, px, py)
    return coords_orig          # (29, 2) en pixels image originale


# ─────────────────────────────────────────────────────────────────
# LIFESPAN — chargement du modèle au démarrage
# ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.path.exists(MODEL_PATH):
        logger.warning(f"⚠️  Modèle introuvable : {MODEL_PATH}  — /predict retournera 503")
    else:
        logger.info(f"📂 Chargement du modèle : {MODEL_PATH}")
        t0 = time.time()
        state.model      = tf.keras.models.load_model(
            MODEL_PATH,
            compile=False,
            custom_objects={"DualAttention": DualAttention},
        )
        state.load_time  = round(time.time() - t0, 2)
        state.model_path = MODEL_PATH
        logger.info(f"✅ Modèle prêt en {state.load_time}s")
    yield
    logger.info("🛑 Arrêt de l'API")


# ─────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Cephalometric Landmark API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────
# SCHÉMAS PYDANTIC
# ─────────────────────────────────────────────────────────────────
class LandmarkPoint(BaseModel):
    id:   int
    name: str
    x:    float          # pixels image originale
    y:    float
    x_mm: float | None = None
    y_mm: float | None = None


class PredictionResponse(BaseModel):
    image_width:  int
    image_height: int
    landmarks:    List[LandmarkPoint]
    inference_ms: float
    tta_passes:   int


class HealthResponse(BaseModel):
    status:       str
    model_loaded: bool
    model_path:   str
    load_time_s:  float


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status       = "ok",
        model_loaded = state.model is not None,
        model_path   = state.model_path,
        load_time_s  = state.load_time,
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict(file: UploadFile = File(...)):
    if state.model is None:
        raise HTTPException(503, "Modèle non chargé — vérifiez MODEL_PATH")

    # ── Lecture de l'image ────────────────────────────────────
    raw_bytes = await file.read()
    arr       = np.frombuffer(raw_bytes, np.uint8)
    img_gray  = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)

    if img_gray is None:
        raise HTTPException(400, "Impossible de décoder l'image. "
                                 "Formats acceptés : PNG, JPG, BMP, TIFF.")

    orig_h, orig_w = img_gray.shape

    # ── Letterbox + inférence TTA ─────────────────────────────
    t0                   = time.perf_counter()
    img_lb, sc, pad_x, pad_y = letterbox_resize(img_gray, IMG_SIZE)
    coords_orig          = predict_tta(state.model, img_lb, sc, pad_x, pad_y)
    inference_ms         = round((time.perf_counter() - t0) * 1000, 1)

    # ── Construction de la réponse ────────────────────────────
    landmarks = []
    for idx, (x, y) in enumerate(coords_orig):
        x_clipped = float(np.clip(x, 0, orig_w - 1))
        y_clipped = float(np.clip(y, 0, orig_h - 1))
        landmarks.append(LandmarkPoint(
            id   = idx + 1,
            name = LANDMARK_NAMES.get(idx + 1, f"LM_{idx+1}"),
            x    = round(x_clipped, 2),
            y    = round(y_clipped, 2),
            x_mm = round(x_clipped * PIXEL_SPACING_MM, 3),
            y_mm = round(y_clipped * PIXEL_SPACING_MM, 3),
        ))

    logger.info(f"✅ {file.filename} | {orig_w}×{orig_h}px | {inference_ms} ms")

    return PredictionResponse(
        image_width  = orig_w,
        image_height = orig_h,
        landmarks    = landmarks,
        inference_ms = inference_ms,
        tta_passes   = len(TTA_SCALES) * len(TTA_ANGLES),
    )