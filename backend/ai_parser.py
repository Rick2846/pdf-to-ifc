"""OpenAI API を用いて自然言語から壁パラメータ JSON を抽出するモジュール."""

from __future__ import annotations

import json
import os

from openai import OpenAI

SYSTEM_PROMPT = """\
あなたは建築BIMアシスタントです。
ユーザーの自然言語による壁の記述を解析し、IFC生成に必要なJSONパラメータを出力してください。

出力形式（厳守）:
{
  "walls": [
    {
      "start_point": {"x": <数値>, "y": <数値>},
      "end_point": {"x": <数値>, "y": <数値>},
      "height": <高さmm>,
      "thickness": <厚みmm>
    }
  ],
  "scale_factor": <スケール係数>
}

変換ルール:
- ユーザーが「幅Xm」「長さXm」と言った場合、start_point=(0,0)、end_point=(X*1000, 0) とする（m→mm変換）。
- 複数の壁が記述された場合、前の壁の end_point を次の壁の start_point として連結する。
- 高さの指定がない場合、デフォルト 3000mm。
- 厚みの指定がない場合、デフォルト 200mm。
- scale_factor は常に 1.0（座標は既にmmなので変換不要）。
- 「直角に」「L字型」等の指示があれば方向を90度回転する。
- JSON以外のテキストは出力しないこと。
"""

WALL_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "wall_parameters",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "walls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start_point": {
                                "type": "object",
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                },
                                "required": ["x", "y"],
                                "additionalProperties": False,
                            },
                            "end_point": {
                                "type": "object",
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                },
                                "required": ["x", "y"],
                                "additionalProperties": False,
                            },
                            "height": {"type": "number"},
                            "thickness": {"type": "number"},
                        },
                        "required": [
                            "start_point",
                            "end_point",
                            "height",
                            "thickness",
                        ],
                        "additionalProperties": False,
                    },
                },
                "scale_factor": {"type": "number"},
            },
            "required": ["walls", "scale_factor"],
            "additionalProperties": False,
        },
    },
}


def parse_walls_from_text(text: str) -> dict:
    """自然言語テキストから壁パラメータ辞書を返す。

    Returns:
        {"walls": [...], "scale_factor": float}

    Raises:
        ValueError: AIがパラメータを抽出できなかった場合
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY が設定されていません。backend/.env を確認してください。")

    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-5.4-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format=WALL_SCHEMA,
        temperature=0.2,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("AIからの応答が空でした。入力テキストを変えて再試行してください。")

    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"AIの応答をJSONとして解析できませんでした: {e}")

    if not result.get("walls"):
        raise ValueError(
            "壁のパラメータを抽出できませんでした。"
            "「高さ3m、幅5mの壁を作って」のように具体的に入力してください。"
        )

    return result
