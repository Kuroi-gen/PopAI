"""
config.py
Azure OpenAI 認証情報 + ダミーモードの設定ファイル。

【ダミーモードから本番への切り替え】
  USE_DUMMY_API = True  → ダミー応答（課金なし / GUI テスト用）
  USE_DUMMY_API = False → 実際の Azure OpenAI API を呼び出す

【認証情報の設定方法】
  A) 環境変数（推奨）:
     $env:AZURE_OPENAI_ENDPOINT        = "https://YOUR_RESOURCE.openai.azure.com/"
     $env:AZURE_OPENAI_API_KEY         = "your_api_key_here"
     $env:AZURE_OPENAI_DEPLOYMENT_NAME = "your_deployment_name"
     $env:AZURE_OPENAI_API_VERSION     = "2024-02-01"

  B) このファイルを直接編集（開発時のみ）
"""

import os

# ── ダミー API スイッチ ──────────────────────────────────────────────
# True  → ダミー応答を返す（課金なし、GUI テスト用）
# False → 実際の Azure OpenAI API を呼び出す
USE_DUMMY_API: bool = True

# ── Azure OpenAI 認証情報 ────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT",
    "https://YOUR_RESOURCE.openai.azure.com/"   # ← 書き換えてください
)

AZURE_OPENAI_API_KEY = os.getenv(
    "AZURE_OPENAI_API_KEY",
    "YOUR_API_KEY_HERE"                         # ← 書き換えてください
)

AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv(
    "AZURE_OPENAI_DEPLOYMENT_NAME",
    "YOUR_DEPLOYMENT_NAME"                      # ← デプロイメント名を入力
)

AZURE_OPENAI_API_VERSION = os.getenv(
    "AZURE_OPENAI_API_VERSION",
    "2024-02-01"
)
