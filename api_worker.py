"""
api_worker.py
Azure OpenAI API との通信を担当する QThread サブクラス。
config.USE_DUMMY_API = True の間はダミー応答を返す。
"""

import time
from PyQt6.QtCore import QThread, pyqtSignal

import config


# ── ボタンキー → システムプロンプト / ラベルのマッピング ─────────────
SYSTEM_PROMPTS: dict[str, str] = {
    "S": "以下の文章を簡潔に要約してください。",
    "Q": "以下の内容に関する質問に答えるか、詳細を解説してください。",
    "J": "以下の文章を自然な日本語に翻訳してください。",
    "C": "",   # チャット: システムプロンプトなし
}

BUTTON_LABELS: dict[str, str] = {
    "S": "要約",
    "Q": "質問",
    "J": "和訳",
    "C": "チャット",
}


# ================================================================== #
# ダミー処理クラス
# ================================================================== #
class DummyApiClient:
    """
    Azure OpenAI の代替となるダミークライアント。
    time.sleep(2) で通信遅延をシミュレートし、
    ダミーテキストを返す。
    """

    def generate(self, button_key: str, user_text: str) -> str:
        label = BUTTON_LABELS.get(button_key, button_key)
        char_count = len(user_text)

        # 通信遅延のシミュレート（2秒）
        time.sleep(2)

        dummy_response = (
            f"[{label}] のダミー回答です。\n\n"
            f"受け取ったテキストの文字数: {char_count} 文字\n\n"
            f"--- 受け取ったテキスト（先頭100文字）---\n"
            f"{user_text[:100]}{'...' if char_count > 100 else ''}\n\n"
            f"※ USE_DUMMY_API = True のため実際のAPIは呼び出されていません。\n"
            f"  本番に切り替えるには config.py の USE_DUMMY_API を False にしてください。"
        )
        return dummy_response


# ================================================================== #
# API ワーカースレッド
# ================================================================== #
class ApiWorker(QThread):
    """
    API呼び出しを非同期で処理する QThread。
    config.USE_DUMMY_API に応じてダミー/本番を切り替える。

    シグナル:
        result_ready(str)   – 回答テキスト
        error_occurred(str) – エラーメッセージ
    """

    result_ready   = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, button_key: str, user_text: str, parent=None):
        super().__init__(parent)
        self._button_key = button_key
        self._user_text  = user_text

    def run(self):
        try:
            if config.USE_DUMMY_API:
                # ── ダミーモード ──────────────────────────────────────
                print(f"[PopAI API] ダミーモード key={self._button_key}, "
                      f"chars={len(self._user_text)}")
                client = DummyApiClient()
                answer = client.generate(self._button_key, self._user_text)

            else:
                # ── 本番モード（Azure OpenAI） ────────────────────────
                from openai import AzureOpenAI

                client = AzureOpenAI(
                    azure_endpoint = config.AZURE_OPENAI_ENDPOINT,
                    api_key        = config.AZURE_OPENAI_API_KEY,
                    api_version    = config.AZURE_OPENAI_API_VERSION,
                )
                system_prompt = SYSTEM_PROMPTS.get(self._button_key, "")
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": self._user_text})

                print(f"[PopAI API] リクエスト送信 key={self._button_key}, "
                      f"deployment={config.AZURE_OPENAI_DEPLOYMENT_NAME}, "
                      f"chars={len(self._user_text)}")

                response = client.chat.completions.create(
                    model    = config.AZURE_OPENAI_DEPLOYMENT_NAME,
                    messages = messages,
                )
                answer = response.choices[0].message.content or ""

            print(f"[PopAI API] 完了 ({len(answer)} 文字)")
            self.result_ready.emit(answer)

        except Exception as e:
            err_msg = f"❌ エラーが発生しました:\n{type(e).__name__}: {e}"
            print(f"[PopAI API] {err_msg}")
            self.error_occurred.emit(err_msg)
