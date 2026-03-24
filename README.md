# 自然言語・UI操作からのIFC自動生成 PoC

ブラウザ上で **Canvas UIによる壁描画** と **自然言語入力（AIチャット）** の両方から、IFC4 形式の 3D 壁モデルを生成・ダウンロードする概念実証システムです。

## アーキテクチャ

```
┌───────────────┐    JSON     ┌──────────────┐    JSON     ┌────────────────┐
│  Canvas UI    │ ──────────► │              │ ──────────► │                │
│ (壁の描画)     │             │   FastAPI    │             │  IfcOpenShell  │
├───────────────┤             │   Backend    │             │  IFC生成       │
│  AI チャット   │ ──text───► │              │             │                │
│ (自然言語入力) │             │  OpenAI API  │             │                │
└───────────────┘             └──────────────┘             └────────────────┘
```

## ディレクトリ構成

```
pdf-to-ifc/
├── backend/
│   ├── .env                # OpenAI APIキー (git管理外)
│   ├── requirements.txt
│   ├── main.py             # FastAPI アプリ
│   ├── ifc_generator.py    # IFC 生成ロジック
│   └── ai_parser.py        # OpenAI による自然言語→壁パラメータ変換
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

`.env` ファイルを作成し、OpenAI APIキーを設定:

```
OPENAI_API_KEY=sk-proj-xxxx
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

### Canvas UI（壁の手動描画）

1. 「Canvas UI」タブを選択
2. 「図面画像を読み込む」で平面図画像をアップロード（任意）
3. Canvas 上をクリックして壁の始点→終点を指定（複数壁追加可能）
4. 右パネルで高さ・厚み・スケール係数を調整
5. 「IFC 生成 & ダウンロード」ボタンを押下

### AI チャット（自然言語入力）

1. 「AI チャット」タブを選択
2. テキスト入力欄に壁の記述を入力（例: 「高さ3m、幅5mの壁を作って」）
3. AIが壁パラメータを解析し、右パネルにJSONを表示
4. 内容を確認後「この内容でIFC生成 & ダウンロード」を押下

## API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/generate-ifc` | 壁パラメータJSON → IFCファイル生成 |
| POST | `/api/parse-walls` | 自然言語テキスト → 壁パラメータJSON |
