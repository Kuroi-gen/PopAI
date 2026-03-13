import os
import sys
import unittest
from unittest.mock import patch, MagicMock

class DummyQThread:
    def __init__(self, parent=None):
        pass

# PyQt6 などをモックする（GUIを起動せずにテストするため）
sys.modules['PyQt6'] = MagicMock()
sys.modules['PyQt6.QtCore'] = MagicMock()
sys.modules['PyQt6.QtCore'].QThread = DummyQThread # 継承できるようにダミークラスにする
sys.modules['dotenv'] = MagicMock()
sys.modules['httpx'] = MagicMock()
sys.modules['openai'] = MagicMock()

# configモジュールをインポート前にモックする
import config
config.USE_DUMMY_API = False
config.AZURE_OPENAI_ENDPOINT = "https://dummy.openai.azure.com/"
config.AZURE_OPENAI_API_KEY = "dummy_key"
config.AZURE_OPENAI_DEPLOYMENT_NAME = "dummy_deployment"
config.AZURE_OPENAI_API_VERSION = "2024-02-01"
config.DISABLE_SSL_VERIFY = False

import httpx
import openai
from api_worker import ApiWorker

# emit用のモック
ApiWorker.result_ready = MagicMock()
ApiWorker.error_occurred = MagicMock()

class TestApiWorkerProxy(unittest.TestCase):

    @patch('httpx.Client')
    @patch('openai.AzureOpenAI')
    def test_proxy_kwargs_with_http(self, mock_azure, mock_httpx_client):
        worker = ApiWorker(button_key="C", user_text="Hello")

        with patch.dict(os.environ, {"HTTP_PROXY": "http://my.proxy:8080"}, clear=True):
            import api_worker
            api_worker._azure_client = None  # Reset cache for testing
            worker.run()
            mock_httpx_client.assert_called_with(proxy="http://my.proxy:8080")

    @patch('httpx.Client')
    @patch('openai.AzureOpenAI')
    def test_proxy_kwargs_with_https(self, mock_azure, mock_httpx_client):
        worker = ApiWorker(button_key="C", user_text="Hello")

        with patch.dict(os.environ, {"HTTPS_PROXY": "https://my.secure.proxy:8443", "HTTP_PROXY": "http://my.proxy:8080"}, clear=True):
            import api_worker
            api_worker._azure_client = None  # Reset cache for testing
            worker.run()
            mock_httpx_client.assert_called_with(proxy="https://my.secure.proxy:8443")

    @patch('httpx.Client')
    @patch('openai.AzureOpenAI')
    def test_proxy_kwargs_no_proxy(self, mock_azure, mock_httpx_client):
        worker = ApiWorker(button_key="C", user_text="Hello")

        with patch.dict(os.environ, {}, clear=True):
            import api_worker
            api_worker._azure_client = None  # Reset cache for testing
            worker.run()
            mock_httpx_client.assert_called_with()

    @patch('httpx.Client')
    @patch('openai.AzureOpenAI')
    def test_proxy_kwargs_with_disable_ssl(self, mock_azure, mock_httpx_client):
        worker = ApiWorker(button_key="C", user_text="Hello")

        # 実行時に config.DISABLE_SSL_VERIFY = True になるように一時的に変更
        orig_val = getattr(config, "DISABLE_SSL_VERIFY", False)
        config.DISABLE_SSL_VERIFY = True
        try:
            with patch.dict(os.environ, {"HTTP_PROXY": "http://my.proxy:8080"}, clear=True):
                import api_worker
                api_worker._azure_client = None  # Reset cache for testing
                worker.run()
                mock_httpx_client.assert_called_with(proxy="http://my.proxy:8080", verify=False)
        finally:
            config.DISABLE_SSL_VERIFY = orig_val

if __name__ == '__main__':
    unittest.main()
