# PopAI セットアップ手順書

このドキュメントは、PopAI（Azure OpenAI連携デスクトップアシスタント）を新しいWindows 11環境で動作させるためのセットアップ手順を説明します。

---

## 1. 事前準備（必要なソフトウェア）

### Pythonのインストール
Pythonがインストールされていない場合は、まずインストールを行ってください。

- **推奨バージョン**: Python 3.10 または 3.11
- **ダウンロードURL**: [Python公式ダウンロードページ (Windows)](https://www.python.org/downloads/windows/)

⚠️ **インストール時の超重要事項**
インストーラーを起動した直後の最初の画面下部にある **「Add python.exe to PATH」**（または「Add Python x.x to PATH」）のチェックボックスに **必ずチェックを入れて** から `Install Now` をクリックしてください。これを行わないとコマンドプロンプトでPythonが実行できません。

---

## 2. ソースコードの配置

以下のいずれかの方法でソースコードをダウンロードします。

### 方法A: GitHubからクローンする場合（Gitがインストールされている場合・推奨）
コマンドプロンプトまたはPowerShellを開き、以下のコマンドを実行します。
```cmd
git clone https://github.com/Kuroi-gen/PopAI.git
cd PopAI
```

### 方法B: ZIPでダウンロードする場合
1. GitHubリポジトリ（https://github.com/Kuroi-gen/PopAI）へアクセスします。
2. 緑色の「Code」ボタンをクリックし、「Download ZIP」を選択します。
3. ダウンロードしたファイルを任意の場所（例：ドキュメントフォルダ）に展開(解凍)します。
4. コマンドプロンプトまたはPowerShellを開き、解凍した `PopAI` フォルダへ移動します。
   ```cmd
   cd C:\Users\あなたのユーザー名\Documents\PopAI
   ```

---

## 3. 必要なライブラリのインストール

アプリケーションの動作に必要な外部ライブラリをインストールします。
コマンドプロンプト（またはPowerShell）で以下のコマンドを実行してください。

```cmd
pip install -r requirements.txt
```

> **含まれる主なライブラリ**
> - `PyQt6`: GUIフレームワーク（フロートウィンドウやシステムトレイの表示）
> - `pynput`: グローバルショートカット（Ctrl+Alt+Space）の監視
> - `pyautogui`: クリップボード取得のためのキーシミュレーション（一部利用）
> - `openai`: Azure OpenAIとの通信APIクライアント
> - `python-dotenv`: `.env` ファイルからの環境変数読み込み

---

## 4. 設定ファイルの準備

Azure OpenAIのAPIキーなどを設定するために `.env` ファイルを作成します。

1. `PopAI` フォルダ（main.pyなどがあるのと同じ場所）に、新規テキストファイルを作成し、名前を **`.env`** としてください。（※最初の文字がドット「.」です）
2. 作成した `.env` ファイルをメモ帳などで開き、以下のテンプレートを貼り付けて、ご自身の環境に合わせて値を書き換えます。

```env
# ====== PopAI 動作設定 ======
# True: ダミーAPIモード（課金なし・UIテスト用） / False: 本番のAzure OpenAIと通信
USE_DUMMY_API=True

# ====== Azure OpenAI 認証情報 ======
AZURE_OPENAI_ENDPOINT="https://YOUR_RESOURCE.openai.azure.com/"
AZURE_OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
AZURE_OPENAI_DEPLOYMENT_NAME="your_deployment_name"
AZURE_OPENAI_API_VERSION="2024-02-01"
```

※まずは `USE_DUMMY_API=True` のままで起動し、UIが問題なく動くか（フリーズしないか等）を確認することをお勧めします。

---

## 5. アプリケーションの起動方法

1. コマンドプロンプト（またはPowerShell）で `PopAI` フォルダに移動した状態にします。
2. 以下のコマンドを実行します。

```cmd
python main.py
```

3. 起動すると、画面右下のタスクトレイ（時計の横）にアイコンが表示され、バックグラウンド待機状態になります。
4. 適当なテキストを選択（ハイライト）した状態で `Ctrl + Alt + Space` キーを押し、**すべての指を離す**と、画面中央にフロートウィンドウが表示されます。

---

## 6. Windows固有の注意事項（トラブルシューティング）

- **ショートカットキーが効かない場合**
  現在フォーカスが当たっている（一番手前にある）アプリケーションが、ゲームなどの排他的なフルスクリーンアプリであったり、管理者権限で実行されているアプリである場合、ショートカットを検知できないことがあります。
  その場合は、PopAIを起動しているコマンドプロンプトやPowerShell自体を**「管理者として実行」**して起動し直すことで解決する場合があります。
  
- **テキストが取得できない（空になる、または直前の文字になる）場合**
  本アプリは「ユーザーがショートカットキーから指をすべて離した瞬間」に `Ctrl + C` を内部的に送信してクリップボードを取得する仕組みになっています。キーを押しっぱなしにせず、ポンっと押してサッと離すようにしてください。
