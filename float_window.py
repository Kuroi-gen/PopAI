"""
float_window.py
クリップボード内容を表示し、Azure OpenAI API の結果を表示するフロートウィンドウ。
最前面・フレームレスで画面中央（またはマウス位置付近）に表示される。
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QSizePolicy, QFrame,
    QApplication, QSizeGrip
)
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtCore import Qt, QPoint, QSettings, QSize
from PyQt6.QtGui import QCursor, QKeySequence, QShortcut, QColor, QWheelEvent, QKeyEvent

from api_worker import ApiWorker, SYSTEM_PROMPTS


class FloatWindow(QWidget):
    """
    フロートポップアップウィンドウ（2ペイン構成）。
    上段: 入力テキスト (クリップボード)
    下段: AI 回答 / ローディング / エラー表示
    """

    BUTTONS = [
        ("要約(&S)", "S", "#4CAF50", "選択テキストを要約します (Alt+S)"),
        ("質問(&Q)", "Q", "#2196F3", "選択テキストについて質問します (Alt+Q)"),
        ("添削(&T)", "T", "#FF9800", "選択テキストを添削します (Alt+T)"),
        ("チャット(&C)", "C", "#9C27B0", "チャットを開始します (Alt+C)"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_pos: QPoint | None = None
        self._api_worker: ApiWorker | None = None
        self._buttons: list[QPushButton] = []

        # 会話履歴を保持するリスト
        self._chat_history: list[dict[str, str]] = []

        # フォントサイズ保持用 (単位: pt)
        self._current_font_size: int = 12

        self._init_ui()
        self._apply_style()

        # フォントサイズ変更（Ctrl + ホイール）をテキストエリアでブロックしないよう設定
        self._input_area.installEventFilter(self)
        self._result_area.installEventFilter(self)

        shortcut = QShortcut(QKeySequence("Escape"), self)
        shortcut.activated.connect(self.close)

        # 履歴クリアのショートカット (Ctrl + L)
        clear_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        clear_shortcut.activated.connect(self._on_clear_clicked)

    def _get_settings(self) -> QSettings:
        # プロジェクトフォルダ内の settings.ini を指定
        settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.ini")
        return QSettings(settings_path, QSettings.Format.IniFormat)

    def _save_settings(self):
        settings = self._get_settings()
        settings.setValue("window/size", self.size())
        settings.setValue("window/pos", self.pos())
        settings.sync()

    def _center_on_primary_screen(self):
        screen = QApplication.primaryScreen().geometry()
        x = screen.left() + (screen.width() - self.width()) // 2
        y = screen.top() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def _ensure_visible(self):
        """
        ウィンドウの中心点が現在有効なディスプレイのいずれかに含まれているか確認し、
        含まれていなければプライマリスクリーンの中央にリセットする。
        """
        center_point = self.geometry().center()
        is_visible = False
        for screen in QApplication.screens():
            if screen.geometry().contains(center_point):
                is_visible = True
                break

        if not is_visible:
            self._center_on_primary_screen()

    def _load_settings_and_apply(self):
        settings = self._get_settings()
        saved_size = settings.value("window/size")
        saved_pos = settings.value("window/pos")

        if saved_size is not None and saved_pos is not None:
            self.resize(saved_size)
            self.move(saved_pos)
            self._ensure_visible()
        else:
            # 初回起動時等のフォールバック
            self.resize(600, 450)
            self._center_on_primary_screen()

    # ------------------------------------------------------------------ #
    # UI 構築
    # ------------------------------------------------------------------ #
    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._container = QWidget(self)
        self._container.setObjectName("container")
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        # ── タイトルバー ──
        title_bar = QHBoxLayout()
        title_label = QLabel("📋  PopAI")
        title_label.setObjectName("titleLabel")
        title_bar.addWidget(title_label)
        title_bar.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.close)
        title_bar.addWidget(close_btn)
        layout.addLayout(title_bar)

        # ── 入力テキストエリア ──
        input_label = QLabel("📄 選択テキスト")
        input_label.setObjectName("sectionLabel")
        layout.addWidget(input_label)

        self._input_area = QTextEdit()
        self._input_area.setObjectName("inputArea")
        self._input_area.setPlaceholderText("クリップボードのテキストがここに表示されます...")
        self._input_area.setMinimumHeight(150)
        self._input_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._input_area)

        # ── ボタン行 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        for label, key, color, tip in self.BUTTONS:
            btn = self._make_button(label, key, color, tip)
            btn_layout.addWidget(btn)
            self._buttons.append(btn)

        # クリアボタンを追加
        clear_btn = QPushButton("🗑️")
        clear_btn.setToolTip("会話履歴をクリアします (Ctrl+L)")
        clear_btn.setFixedHeight(36)
        clear_btn.setFixedWidth(40)
        clear_btn.setObjectName("btnClear")
        clear_btn.clicked.connect(self._on_clear_clicked)
        btn_layout.addWidget(clear_btn)
        self._clear_btn = clear_btn

        layout.addLayout(btn_layout)

        # ── セパレータ ──
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── AI 回答エリア ──
        result_label = QLabel("🤖 AI の回答")
        result_label.setObjectName("sectionLabel")
        layout.addWidget(result_label)

        self._result_area = QTextEdit()
        self._result_area.setObjectName("resultArea")
        self._result_area.setReadOnly(True)
        self._result_area.setPlaceholderText("ボタンを押すと AI の回答がここに表示されます...")
        self._result_area.setMinimumHeight(120)
        self._result_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._result_area)

        root_layout.addWidget(self._container)

        # ── QSizeGrip を右下に追加 ──
        # QSizeGripを確実に機能させ、背面に隠れないように_containerのレイアウトではなく、
        # _containerに直接重ねるような配置にします。（QSizeGripの親をselfにして、resizeEventで右下に配置）

        # QSizeGrip を作成（親を self に設定）
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)

        # 背景と重なって見えなくなるのを防ぐため、少し色をつけます
        self.size_grip.setStyleSheet("QSizeGrip { background-color: rgba(255, 255, 255, 0.3); border-radius: 4px; }")

        self.setMinimumWidth(400)
        self.setMinimumHeight(300)

        # ── 前回サイズ・位置の復元 ──
        self._load_settings_and_apply()

        # ── アプリ終了時にも保存する ──
        QApplication.instance().aboutToQuit.connect(self._save_settings)

    def _make_button(self, label: str, key: str, color: str, tip: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setToolTip(tip)
        btn.setFixedHeight(36)
        btn.setObjectName(f"btn_{key}")
        btn.setProperty("btnColor", color)
        btn.clicked.connect(lambda _, k=key: self._on_button_clicked(k))
        return btn

    # ------------------------------------------------------------------ #
    # スタイル
    # ------------------------------------------------------------------ #
    def _apply_style(self):
        self.setStyleSheet(f"""
            QWidget#container {{
                background-color: rgba(22, 22, 30, 230);
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 0.10);
            }}

            QLabel#titleLabel {{
                color: #E0E0E0;
                font-size: 14px;
                font-weight: bold;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
            }}

            QLabel#sectionLabel {{
                color: #888;
                font-size: 11px;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
            }}

            QPushButton#closeBtn {{
                background: transparent;
                color: #888;
                border: none;
                font-size: 14px;
                border-radius: 14px;
            }}
            QPushButton#closeBtn:hover {{ background: rgba(255,80,80,0.3); color:#fff; }}

            QTextEdit#inputArea {{
                background-color: rgba(10, 10, 18, 180);
                color: #C8C8C8;
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 8px;
                font-family: "Consolas", "Yu Gothic UI", monospace;
                font-size: {self._current_font_size}pt;
                padding: 8px;
                selection-background-color: #264F78;
            }}

            QFrame#separator {{
                color: rgba(255,255,255,0.08);
                max-height: 1px;
                background: rgba(255,255,255,0.08);
            }}

            QTextEdit#resultArea {{
                background-color: rgba(10, 10, 18, 200);
                color: #D4D4D4;
                border: 1px solid rgba(156, 39, 176, 0.3);
                border-radius: 8px;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
                font-size: {self._current_font_size}pt;
                padding: 10px;
                selection-background-color: #264F78;
            }}

            QPushButton[btnColor="#4CAF50"] {{
                background-color: #4CAF50; color:white; border:none;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:12pt;
            }}
            QPushButton[btnColor="#4CAF50"]:hover   {{ background-color:#66BB6A; }}
            QPushButton[btnColor="#4CAF50"]:pressed  {{ background-color:#388E3C; }}
            QPushButton[btnColor="#4CAF50"]:disabled {{ background-color:#2E5E30; color:#666; }}

            QPushButton[btnColor="#2196F3"] {{
                background-color: #2196F3; color:white; border:none;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:12pt;
            }}
            QPushButton[btnColor="#2196F3"]:hover   {{ background-color:#42A5F5; }}
            QPushButton[btnColor="#2196F3"]:pressed  {{ background-color:#1565C0; }}
            QPushButton[btnColor="#2196F3"]:disabled {{ background-color:#1A3A6E; color:#666; }}

            QPushButton[btnColor="#FF9800"] {{
                background-color: #FF9800; color:white; border:none;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:12pt;
            }}
            QPushButton[btnColor="#FF9800"]:hover   {{ background-color:#FFA726; }}
            QPushButton[btnColor="#FF9800"]:pressed  {{ background-color:#E65100; }}
            QPushButton[btnColor="#FF9800"]:disabled {{ background-color:#7A4A00; color:#666; }}

            QPushButton[btnColor="#9C27B0"] {{
                background-color: #9C27B0; color:white; border:none;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:12pt;
            }}
            QPushButton[btnColor="#9C27B0"]:hover   {{ background-color:#AB47BC; }}
            QPushButton[btnColor="#9C27B0"]:pressed  {{ background-color:#6A1B9A; }}
            QPushButton[btnColor="#9C27B0"]:disabled {{ background-color:#4A1260; color:#666; }}

            QPushButton#btnClear {{
                background-color: transparent;
                color: #888;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                font-size: 14pt;
            }}
            QPushButton#btnClear:hover {{
                background-color: rgba(255, 80, 80, 0.2);
                border-color: rgba(255, 80, 80, 0.5);
                color: white;
            }}
            QPushButton#btnClear:pressed {{
                background-color: rgba(255, 80, 80, 0.4);
            }}
            QPushButton#btnClear:disabled {{
                background-color: rgba(255, 255, 255, 0.05);
                color: #666;
            }}
        """)

    # ------------------------------------------------------------------ #
    # 公開 API
    # ------------------------------------------------------------------ #
    def show_with_text(self, text: str):
        """テキストをセットしてウィンドウを表示する。"""
        self._input_area.setPlainText(text)

        # 履歴をクリアして新しいテキストでの開始に備える
        self._chat_history.clear()

        self._result_area.clear()
        self._set_buttons_enabled(True)

        if self.isHidden():
            # 非表示状態から復帰する際は設定を読み込んで適用
            self._load_settings_and_apply()
        else:
            # すでに表示されている場合でも、画面外に移動していないか確認
            self._ensure_visible()

        self.show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------ #
    # ボタンアクション
    # ------------------------------------------------------------------ #
    def _on_clear_clicked(self):
        # 履歴をクリア
        self._chat_history.clear()

        # UIをリセット（テキストエリア下段のみ）
        self._result_area.setPlainText("🧹 会話履歴をクリアしました")

    def _on_button_clicked(self, key: str):
        text = self._input_area.toPlainText().strip()
        if not text:
            self._result_area.setPlainText("⚠️ テキストが入力されていません。")
            return

        # システムプロンプトの管理
        # 常に最新のボタンのシステムプロンプトで先頭を上書き（差し替え）する
        system_prompt = SYSTEM_PROMPTS.get(key, "")

        # 履歴が空、または最初の要素がシステムプロンプトでない場合は新しく追加
        if not self._chat_history or self._chat_history[0].get("role") != "system":
            if system_prompt:
                self._chat_history.insert(0, {"role": "system", "content": system_prompt})
        else:
            # 最初の要素がシステムプロンプトの場合
            if system_prompt:
                self._chat_history[0] = {"role": "system", "content": system_prompt}
            else:
                # system_promptが空（チャットボタンなど）の場合は削除
                self._chat_history.pop(0)

        # ユーザー入力を履歴に追加
        self._chat_history.append({"role": "user", "content": text})

        # 前回のワーカーが残っている場合は終了を待たずに破棄
        if self._api_worker and self._api_worker.isRunning():
            self._api_worker.quit()

        # ローディング表示
        self._result_area.setPlainText("⏳ 処理中...（数秒〜数十秒かかります）\n\n")
        self._set_buttons_enabled(False)

        # ワーカー起動
        self._api_worker = ApiWorker(button_key=key, messages=self._chat_history)
        self._api_worker.result_ready.connect(self._on_result)
        self._api_worker.error_occurred.connect(self._on_error)
        self._api_worker.finished.connect(lambda: self._set_buttons_enabled(True))
        self._api_worker.start()

    def _on_result(self, answer: str):
        # AIの回答を履歴に追加
        self._chat_history.append({"role": "assistant", "content": answer})

        # 一括で結果を描画する
        self._result_area.setPlainText(answer)

        # スクロールバーを一番下に移動する
        scrollbar = self._result_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_error(self, msg: str):
        # エラー時は直前に追加したユーザー入力を取り消す
        if self._chat_history and self._chat_history[-1].get("role") == "user":
            self._chat_history.pop()

        # 最初に来る「⏳ 処理中...（数秒〜数十秒かかります）\n\n」を消すための簡易判定
        current_text = self._result_area.toPlainText()
        if current_text == "⏳ 処理中...（数秒〜数十秒かかります）\n\n":
            self._result_area.clear()

        # エラーメッセージを追記する
        self._result_area.insertPlainText(msg)

        # スクロールバーを一番下に移動する
        scrollbar = self._result_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # エラー時は結果エリアを赤みがかった色にする（スタイルを一時変更）
        self._result_area.setStyleSheet(
            f"QTextEdit {{ color: #FF6B6B; background-color: rgba(80,10,10,200); "
            f"border: 1px solid rgba(255,80,80,0.4); border-radius:8px; "
            f"font-family:'Segoe UI','Yu Gothic UI',sans-serif; font-size:{self._current_font_size}pt; padding:10px; }}"
        )

    def _set_buttons_enabled(self, enabled: bool):
        for btn in self._buttons:
            btn.setEnabled(enabled)
        if hasattr(self, '_clear_btn'):
            self._clear_btn.setEnabled(enabled)

        if enabled:
            # エラー色をリセット
            self._result_area.setStyleSheet("")
            self._apply_style()

    # ------------------------------------------------------------------ #
    # イベントオーバーライド (ドラッグ移動 / フォントサイズ変更)
    # ------------------------------------------------------------------ #
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # QSizeGrip を常に右下に配置する
        self.size_grip.move(self.width() - self.size_grip.width(), self.height() - self.size_grip.height())
        self.size_grip.raise_()

    def eventFilter(self, obj, event):
        # QTextEdit 上の Ctrl+ホイールイベントをキャッチして処理
        if event.type() == event.Type.Wheel and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.wheelEvent(event)
            return True
        return super().eventFilter(obj, event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._current_font_size = min(32, self._current_font_size + 1)
            elif delta < 0:
                self._current_font_size = max(8, self._current_font_size - 1)
            self._apply_style()
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
                self._current_font_size = min(32, self._current_font_size + 1)
                self._apply_style()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Minus:
                self._current_font_size = max(8, self._current_font_size - 1)
                self._apply_style()
                event.accept()
                return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def focusOutEvent(self, event):
        super().focusOutEvent(event)

    def hideEvent(self, event):
        # 非表示になる際にサイズと位置を保存する
        self._save_settings()
        super().hideEvent(event)

    def closeEvent(self, event: QCloseEvent):
        # 閉じる（×）ボタンなどが押された際、破棄せず非表示にする
        event.ignore()
        self.hide()
