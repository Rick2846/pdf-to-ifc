from __future__ import annotations

import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ai_parser import parse_walls_from_text
from ifc_generator import generate_ifc
from image_parser import detect_walls_from_image

load_dotenv()

app = FastAPI(title="PDF-to-IFC PoC")

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


class ParseWallsRequest(BaseModel):
    text: str = Field(..., min_length=1)


class ParseWallsResponse(BaseModel):
    walls: list[Wall]
    scale_factor: float


@app.post("/api/parse-walls", response_model=ParseWallsResponse)
async def parse_walls_endpoint(req: ParseWallsRequest):
    """自然言語テキストから壁パラメータ JSON を抽出する。"""
    try:
        result = parse_walls_from_text(req.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI処理中にエラーが発生しました: {e}")

    return result


@app.post("/api/detect-lines")
async def detect_lines_endpoint(file: UploadFile = File(...)):
    """アップロードされた画像から直線を検出して壁の始点・終点を返す。"""
    try:
        image_bytes = await file.read()
        lines = detect_walls_from_image(image_bytes)
        return {"lines": lines}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"画像解析に失敗しました: {e}")


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
