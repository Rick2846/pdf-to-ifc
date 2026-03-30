# Canvas UI からの IFC 自動生成 PoC

ブラウザ上で **Canvas UI による壁描画** と **図面画像からの線自動検出** から、IFC4 形式の 3D 壁モデルを生成・ダウンロードする概念実証システムです。

## アーキテクチャ

```
┌───────────────┐    JSON     ┌──────────────┐    JSON     ┌────────────────┐
│  Canvas UI    │ ──────────► │              │ ──────────► │                │
│ (壁の描画)     │             │   FastAPI    │             │  IfcOpenShell  │
├───────────────┤             │   Backend    │             │  IFC生成       │
│ 画像アップロード│ ──image──► │ (OpenCV検出)  │             │                │
└───────────────┘             └──────────────┘             └────────────────┘
```

## ディレクトリ構成

```
pdf-to-ifc/
├── backend/
│   ├── requirements.txt
│   ├── main.py             # FastAPI アプリ
│   ├── ifc_generator.py    # IFC 生成ロジック
│   └── image_parser.py     # 画像からの線検出 (OpenCV)
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

## セットアップ

### バックエンド

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

サーバー起動:

```bash
uvicorn main:app --reload --port 8000
```

### フロントエンド

```bash
cd frontend
python -m http.server 3000
```

ブラウザで http://localhost:3000 を開きます。

## 使い方

### Canvas UI（壁の手動描画・画像からの自動認識）

1. 「図面画像を読み込む」で平面図画像をアップロード（任意）
2. Canvas 上をクリックして壁の始点→終点を指定（複数壁追加可能）、または「画像から自動認識」で線を壁として追加
3. 右パネルで高さ・厚み・スケール係数を調整
4. 「すべての壁からIFC生成 & ダウンロード」ボタンを押下

## API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/generate-ifc` | 壁パラメータJSON → IFCファイル生成 |
| POST | `/api/detect-lines` | 画像アップロード → 検出した線（始点・終点）のリスト |
