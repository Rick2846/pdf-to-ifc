from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ifc_generator import generate_ifc

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
