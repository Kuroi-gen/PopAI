"""
float_window.py
クリップボード内容を表示し、Azure OpenAI API の結果を表示するフロートウィンドウ。
最前面・フレームレスで画面中央（またはマウス位置付近）に表示される。
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QCursor, QKeySequence, QShortcut, QColor

from api_worker import ApiWorker


class FloatWindow(QWidget):
    """
    フロートポップアップウィンドウ（2ペイン構成）。
    上段: 入力テキスト (クリップボード)
    下段: AI 回答 / ローディング / エラー表示
    """

    BUTTONS = [
        ("要約 (S)", "S", "#4CAF50", "選択テキストを要約します"),
        ("質問 (Q)", "Q", "#2196F3", "選択テキストについて質問します"),
        ("和訳 (J)", "J", "#FF9800", "選択テキストを日本語に翻訳します"),
        ("チャット (C)", "C", "#9C27B0", "チャットを開始します"),
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

        self._init_ui()
        self._apply_style()

        shortcut = QShortcut(QKeySequence("Escape"), self)
        shortcut.activated.connect(self.close)

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
        self._input_area.setMinimumHeight(90)
        self._input_area.setMaximumHeight(160)
        self._input_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._input_area)

        # ── ボタン行 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        for label, key, color, tip in self.BUTTONS:
            btn = self._make_button(label, key, color, tip)
            btn_layout.addWidget(btn)
            self._buttons.append(btn)
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

        self.setMinimumWidth(520)
        self.setMaximumWidth(760)

    def _make_button(self, label: str, key: str, color: str, tip: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setToolTip(tip)
        btn.setFixedHeight(36)
        btn.setObjectName(f"btn_{key}")
        btn.setProperty("btnColor", color)
        btn.clicked.connect(lambda _, k=key: self._on_button_clicked(k))

        sc = QShortcut(QKeySequence(key), self)
        sc.activated.connect(btn.click)
        return btn

    # ------------------------------------------------------------------ #
    # スタイル
    # ------------------------------------------------------------------ #
    def _apply_style(self):
        self.setStyleSheet("""
            QWidget#container {
                background-color: rgba(22, 22, 30, 230);
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 0.10);
            }

            QLabel#titleLabel {
                color: #E0E0E0;
                font-size: 14px;
                font-weight: bold;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
            }

            QLabel#sectionLabel {
                color: #888;
                font-size: 11px;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
            }

            QPushButton#closeBtn {
                background: transparent;
                color: #888;
                border: none;
                font-size: 14px;
                border-radius: 14px;
            }
            QPushButton#closeBtn:hover { background: rgba(255,80,80,0.3); color:#fff; }

            QTextEdit#inputArea {
                background-color: rgba(10, 10, 18, 180);
                color: #C8C8C8;
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 8px;
                font-family: "Consolas", "Yu Gothic UI", monospace;
                font-size: 12px;
                padding: 8px;
                selection-background-color: #264F78;
            }

            QFrame#separator {
                color: rgba(255,255,255,0.08);
                max-height: 1px;
                background: rgba(255,255,255,0.08);
            }

            QTextEdit#resultArea {
                background-color: rgba(10, 10, 18, 200);
                color: #D4D4D4;
                border: 1px solid rgba(156, 39, 176, 0.3);
                border-radius: 8px;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
                font-size: 13px;
                padding: 10px;
                selection-background-color: #264F78;
            }

            QPushButton[btnColor="#4CAF50"] {
                background-color: #4CAF50; color:white; border:none;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:13px;
            }
            QPushButton[btnColor="#4CAF50"]:hover   { background-color:#66BB6A; }
            QPushButton[btnColor="#4CAF50"]:pressed  { background-color:#388E3C; }
            QPushButton[btnColor="#4CAF50"]:disabled { background-color:#2E5E30; color:#666; }

            QPushButton[btnColor="#2196F3"] {
                background-color: #2196F3; color:white; border:none;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:13px;
            }
            QPushButton[btnColor="#2196F3"]:hover   { background-color:#42A5F5; }
            QPushButton[btnColor="#2196F3"]:pressed  { background-color:#1565C0; }
            QPushButton[btnColor="#2196F3"]:disabled { background-color:#1A3A6E; color:#666; }

            QPushButton[btnColor="#FF9800"] {
                background-color: #FF9800; color:white; border:none;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:13px;
            }
            QPushButton[btnColor="#FF9800"]:hover   { background-color:#FFA726; }
            QPushButton[btnColor="#FF9800"]:pressed  { background-color:#E65100; }
            QPushButton[btnColor="#FF9800"]:disabled { background-color:#7A4A00; color:#666; }

            QPushButton[btnColor="#9C27B0"] {
                background-color: #9C27B0; color:white; border:none;
                border-radius:8px; font-weight:bold;
                font-family:"Segoe UI","Yu Gothic UI",sans-serif; font-size:13px;
            }
            QPushButton[btnColor="#9C27B0"]:hover   { background-color:#AB47BC; }
            QPushButton[btnColor="#9C27B0"]:pressed  { background-color:#6A1B9A; }
            QPushButton[btnColor="#9C27B0"]:disabled { background-color:#4A1260; color:#666; }
        """)

    # ------------------------------------------------------------------ #
    # 公開 API
    # ------------------------------------------------------------------ #
    def show_with_text(self, text: str):
        """テキストをセットしてウィンドウを表示する。"""
        self._input_area.setPlainText(text)
        self._result_area.clear()
        self._set_buttons_enabled(True)

        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        cursor_pos = QCursor.pos()

        self.adjustSize()
        w, h = self.width(), self.height()
        x = max(screen.left(), min(cursor_pos.x() - w // 2, screen.right()  - w))
        y = max(screen.top(),  min(cursor_pos.y() - h // 2, screen.bottom() - h))

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------ #
    # ボタンアクション
    # ------------------------------------------------------------------ #
    def _on_button_clicked(self, key: str):
        text = self._input_area.toPlainText().strip()
        if not text:
            self._result_area.setPlainText("⚠️ テキストが入力されていません。")
            return

        # 前回のワーカーが残っている場合は終了を待たずに破棄
        if self._api_worker and self._api_worker.isRunning():
            self._api_worker.quit()

        # ローディング表示
        self._result_area.setPlainText("⏳ 処理中...")
        self._set_buttons_enabled(False)

        # ワーカー起動
        self._api_worker = ApiWorker(button_key=key, user_text=text)
        self._api_worker.result_ready.connect(self._on_result)
        self._api_worker.error_occurred.connect(self._on_error)
        self._api_worker.finished.connect(lambda: self._set_buttons_enabled(True))
        self._api_worker.start()

    def _on_result(self, answer: str):
        self._result_area.setPlainText(answer)

    def _on_error(self, msg: str):
        self._result_area.setPlainText(msg)
        # エラー時は結果エリアを赤みがかった色にする（スタイルを一時変更）
        self._result_area.setStyleSheet(
            "QTextEdit { color: #FF6B6B; background-color: rgba(80,10,10,200); "
            "border: 1px solid rgba(255,80,80,0.4); border-radius:8px; "
            "font-family:'Segoe UI','Yu Gothic UI',sans-serif; font-size:13px; padding:10px; }"
        )

    def _set_buttons_enabled(self, enabled: bool):
        for btn in self._buttons:
            btn.setEnabled(enabled)
        if enabled:
            # エラー色をリセット
            self._result_area.setStyleSheet("")
            self._apply_style()

    # ------------------------------------------------------------------ #
    # ドラッグ移動
    # ------------------------------------------------------------------ #
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
