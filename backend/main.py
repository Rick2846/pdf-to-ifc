from __future__ import annotations

import base64
import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
import numpy as np
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pdf2image import convert_from_bytes
from pydantic import BaseModel, Field

from ifc_generator import generate_ifc
from image_parser import detect_walls_from_bgr
from models.hg_furukawa import HGFurukawa

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

WEIGHTS_PATH = Path(__file__).resolve().parent / "weights" / "model_best_val_loss_var.pkl"


@asynccontextmanager
async def lifespan(application: FastAPI):
    """起動時に CubiCasa5K モデルを 1 回だけロードし app.state に保持する。"""
    model: HGFurukawa | None = None

    if WEIGHTS_PATH.exists():
        logger.info("Loading CubiCasa5K weights from %s …", WEIGHTS_PATH)
        try:
            model = HGFurukawa(n_classes=HGFurukawa.N_CLASSES)
            checkpoint = torch.load(WEIGHTS_PATH, map_location="cpu", weights_only=False)
            model.load_state_dict(checkpoint["model_state"])
            model.eval()
            logger.info("CubiCasa5K model loaded successfully.")
        except Exception:
            logger.exception("Failed to load CubiCasa5K model – falling back to OpenCV.")
            model = None
    else:
        logger.warning(
            "Weight file not found: %s – wall detection will use OpenCV fallback.",
            WEIGHTS_PATH,
        )

    application.state.cubicasa_model = model
    yield


app = FastAPI(title="PDF-to-IFC PoC", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Point2D(BaseModel):
    x: float
    y: float


class Wall(BaseModel):
    start_point: Point2D
    end_point: Point2D
    height: float = Field(default=3000.0, gt=0)
    thickness: float = Field(default=200.0, gt=0)


class GenerateIfcRequest(BaseModel):
    walls: list[Wall]
    scale_factor: float = Field(default=1.0, gt=0)


def _is_pdf(data: bytes) -> bool:
    return len(data) >= 5 and data[:5] == b"%PDF-"


@app.post("/api/detect-lines")
async def detect_lines_endpoint(file: UploadFile = File(...)):
    """アップロードされた PDF の1ページ目を画像化し、直線検出結果とプレビュー用 Base64 を返す。"""
    try:
        pdf_bytes = await file.read()
        if not _is_pdf(pdf_bytes):
            raise HTTPException(
                status_code=400,
                detail="PDFファイルのみ対応しています。",
            )

        pil_pages = convert_from_bytes(pdf_bytes, dpi=300)
        if not pil_pages:
            raise HTTPException(
                status_code=400,
                detail="PDFからページを読み取れませんでした。",
            )

        pil = pil_pages[0]
        bgr = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)

        model: HGFurukawa | None = getattr(app.state, "cubicasa_model", None)
        walls = detect_walls_from_bgr(bgr, model=model)

        ok, buf = cv2.imencode(".png", bgr)
        if not ok:
            raise HTTPException(
                status_code=500,
                detail="プレビュー画像の生成に失敗しました。",
            )
        image_b64 = base64.b64encode(buf.tobytes()).decode("ascii")

        return {"image": image_b64, "walls": walls}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"PDF解析に失敗しました: {e}",
        ) from e


@app.post("/api/generate-ifc")
async def generate_ifc_endpoint(req: GenerateIfcRequest):
    if not req.walls:
        raise HTTPException(status_code=400, detail="壁データが指定されていません。")

    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".ifc", delete=False)
        tmp.close()
        output_path = Path(tmp.name)

        generate_ifc(req.walls, req.scale_factor, output_path)

        return FileResponse(
            path=str(output_path),
            media_type="application/octet-stream",
            filename="output.ifc",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"IFC生成に失敗しました: {e}")
