# PDF図面 → IFC 簡易3D壁モデル生成 PoC

ブラウザ上で PDF 図面（画像）の2点間をクリックし、高さ・厚みを指定して IFC4 形式の 3D 壁モデルを生成・ダウンロードする概念実証システムです。

## ディレクトリ構成

```
pdf-to-ifc/
├── backend/
│   ├── requirements.txt
│   ├── main.py          # FastAPI アプリ
│   └── ifc_generator.py # IFC 生成ロジック
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
uvicorn main:app --reload --port 8000
```

### フロントエンド

任意の HTTP サーバーで `frontend/` を配信します。

```bash
cd frontend
python -m http.server 3000
```

ブラウザで http://localhost:3000 を開きます。

## 使い方

1. 「図面画像を読み込む」で平面図画像をアップロード（任意）
2. Canvas 上をクリックして壁の始点→終点を指定（複数壁追加可能）
3. 右パネルで高さ・厚み・スケール係数を調整
4. 「IFC 生成 & ダウンロード」ボタンを押下
5. `output.ifc` がダウンロードされます

ダウンロードした `.ifc` ファイルは BIMvision 等の IFC ビューアで確認できます。
