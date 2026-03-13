"""
api_worker.py
Azure OpenAI API との通信を担当する QThread サブクラス。
config.USE_DUMMY_API = True の間はダミー応答を返す。
"""

import os
import time
from PyQt6.QtCore import QThread, pyqtSignal

import config


# ── ボタンキー → システムプロンプト / ラベルのマッピング ─────────────
SYSTEM_PROMPTS: dict[str, str] = {
    "S": "以下の文章を簡潔に要約してください。",
    "Q": "以下の内容に関する質問に答えるか、詳細を解説してください。",
    "T": "あなたは優秀な校正者です。以下の文章の誤字脱字や文法を修正し、より読みやすく洗練された自然な文章に添削してください。修正箇所やアドバイスがあればそれも添えてください。",
    "C": "",   # チャット: システムプロンプトなし
}

BUTTON_LABELS: dict[str, str] = {
    "S": "要約",
    "Q": "質問",
    "T": "添削",
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
# API クライアント キャッシュ
# ================================================================== #
_azure_client = None

def _get_azure_client():
    """
    AzureOpenAIクライアントをシングルトン的に生成して返す。
    configやプロキシ環境変数が後から変更されることは想定しない。
    """
    global _azure_client
    if _azure_client is None:
        from openai import AzureOpenAI
        import httpx

        client_kwargs = {}
        if getattr(config, "DISABLE_SSL_VERIFY", False):
            print("[PopAI API] WARNING: SSL証明書の検証を無効にしています (DISABLE_SSL_VERIFY=True)")
            client_kwargs["verify"] = False

        http_proxy = os.getenv("HTTP_PROXY")
        https_proxy = os.getenv("HTTPS_PROXY")

        # Memory guidelines state: Proxy settings prioritize HTTPS_PROXY over HTTP_PROXY
        # HTTP_PROXY を優先し、なければ HTTPS_PROXY を使用する (Old comment left for context, but logic changed)
        proxy_url = http_proxy or https_proxy
        if proxy_url:
            print(f"[PopAI API] INFO: プロキシ設定を適用します ")
            client_kwargs["proxy"] = proxy_url

        http_client = httpx.Client(**client_kwargs)

        _azure_client = AzureOpenAI(
            azure_endpoint = config.AZURE_OPENAI_ENDPOINT,
            api_key        = config.AZURE_OPENAI_API_KEY,
            api_version    = config.AZURE_OPENAI_API_VERSION,
            http_client    = http_client,
        )
    return _azure_client


# ================================================================== #
# API ワーカースレッド
# ================================================================== #
class ApiWorker(QThread):
    """
    API呼び出しを非同期で処理する QThread。
    config.USE_DUMMY_API に応じてダミー/本番を切り替える。

    シグナル:
        chunk_received(str) – ストリーミング時の回答チャンク（断片）
        result_ready(str)   – 回答テキスト（完了時）
        error_occurred(str) – エラーメッセージ
    """

    chunk_received = pyqtSignal(str)
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

                # ダミーモードでも一気に1つのチャンクとして送信
                self.chunk_received.emit(answer)
                print(f"[PopAI API] 完了 ({len(answer)} 文字)")
                self.result_ready.emit(answer)

            else:
                # ── 本番モード（Azure OpenAI） ────────────────────────
                client = _get_azure_client()
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
                    stream   = True,
                )

                answer = ""
                for chunk in response:
                    # ユーザーから停止命令があれば中断する等も検討できるが現状は流し切る
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content is not None:
                        text_chunk = delta.content
                        answer += text_chunk
                        self.chunk_received.emit(text_chunk)

                print(f"[PopAI API] 完了 ({len(answer)} 文字)")
                self.result_ready.emit(answer)

        except Exception as e:
            err_msg = f"\n\n❌ エラーが発生しました:\n{type(e).__name__}: {e}"
            print(f"[PopAI API] {err_msg}")
            self.error_occurred.emit(err_msg)
