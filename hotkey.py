"""
hotkey.py
グローバルホットキー (Ctrl+Alt+Space) を監視するスレッド。
検出時に前のウィンドウへ Ctrl+C を送信し、クリップボード内容をシグナルで通知する。
"""

import time
import ctypes
import ctypes.wintypes
import threading
from pynput import keyboard as pynput_kb

from PyQt6.QtCore import QThread, pyqtSignal


import os
from dotenv import load_dotenv

load_dotenv(override=True)

# ------------------------------------------------------------------ #
# 正規化済みホットキーの定義
# ------------------------------------------------------------------ #
def _parse_global_shortcut():
    shortcut_str = os.getenv("GLOBAL_SHORTCUT", "ctrl+shift+space")
    parts = shortcut_str.lower().split('+')

    normalized = set()
    modifiers = set()

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # pynput_kb.Key に存在するかどうかを確認 (例: ctrl, shift, space)
        if hasattr(pynput_kb.Key, part):
            key = getattr(pynput_kb.Key, part)
            normalized.add(key)
            modifiers.add(key)

            # 左右の修飾キーも許可リストに追加
            if part == 'ctrl':
                modifiers.update([pynput_kb.Key.ctrl_l, pynput_kb.Key.ctrl_r])
            elif part == 'alt':
                modifiers.update([pynput_kb.Key.alt_l, pynput_kb.Key.alt_r])
            elif part == 'shift':
                modifiers.update([pynput_kb.Key.shift_l, pynput_kb.Key.shift_r])
        else:
            # それ以外は通常の文字キーとみなす (例: 'c', '1')
            # from_char を使うと KeyCode.from_char('q') となるが、
            # pynput が on_press で渡してくる文字キーと確実に一致するようにする
            key = pynput_kb.KeyCode.from_char(part)
            normalized.add(key)

    return frozenset(normalized), frozenset(modifiers), shortcut_str

HOTKEY_NORMALIZED, HOTKEY_MODIFIERS, HOTKEY_STRING = _parse_global_shortcut()


# ------------------------------------------------------------------ #
# Windows API ラッパー
# ------------------------------------------------------------------ #
_user32   = ctypes.WinDLL('user32', use_last_error=True)
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# restype 明示（64bit でポインタが切り捨てられないようにする）
_user32.GetForegroundWindow.restype  = ctypes.wintypes.HWND
_user32.SetForegroundWindow.argtypes = [ctypes.wintypes.HWND]
_user32.GetClipboardData.restype     = ctypes.c_void_p
_kernel32.GlobalLock.restype         = ctypes.c_void_p
_kernel32.GlobalLock.argtypes        = [ctypes.c_void_p]
_kernel32.GlobalUnlock.argtypes      = [ctypes.c_void_p]


# ------------------------------------------------------------------ #
# INPUT 構造体（64bit 対応: WPARAM = UINT_PTR = 8 bytes on x64）
# sizeof(INPUT) must be 40 on x64 Windows
# ------------------------------------------------------------------ #
# dwExtraInfo は ULONG_PTR → WPARAM (c_size_t と同じポインタサイズ)
_WPARAM = ctypes.wintypes.WPARAM   # c_uint64 on 64-bit

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk',         ctypes.wintypes.WORD),
        ('wScan',       ctypes.wintypes.WORD),
        ('dwFlags',     ctypes.wintypes.DWORD),
        ('time',        ctypes.wintypes.DWORD),
        ('dwExtraInfo', _WPARAM),
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx',          ctypes.wintypes.LONG),
        ('dy',          ctypes.wintypes.LONG),
        ('mouseData',   ctypes.wintypes.DWORD),
        ('dwFlags',     ctypes.wintypes.DWORD),
        ('time',        ctypes.wintypes.DWORD),
        ('dwExtraInfo', _WPARAM),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ('uMsg',    ctypes.wintypes.DWORD),
        ('wParamL', ctypes.wintypes.WORD),
        ('wParamH', ctypes.wintypes.WORD),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ('ki', KEYBDINPUT),
        ('mi', MOUSEINPUT),
        ('hi', HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _anonymous_ = ('_u',)
    _fields_ = [
        ('type', ctypes.wintypes.DWORD),
        ('_u',   _INPUT_UNION),
    ]

INPUT_KEYBOARD  = 1
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL      = 0x11
VK_MENU         = 0x12   # Alt
VK_SPACE        = 0x20
VK_C            = 0x43

_sizeof_INPUT = ctypes.sizeof(INPUT)

def _ki(vk: int, flags: int = 0) -> INPUT:
    inp = INPUT()
    inp.type       = INPUT_KEYBOARD
    inp.ki.wVk     = vk
    inp.ki.dwFlags = flags
    return inp

def send_keys(*inputs: INPUT) -> int:
    """SendInput に INPUT 列を渡す。戻り値は送信できたイベント数（0 なら失敗）。"""
    arr = (INPUT * len(inputs))(*inputs)
    n = _user32.SendInput(len(inputs), arr, _sizeof_INPUT)
    if n == 0:
        err = ctypes.get_last_error()
        print(f"[PopAI] SendInput 失敗 (送信数={n}, LastError={err})")
    else:
        print(f"[PopAI] SendInput: {n} イベント送信成功")
    return n

def release_hotkey_keys() -> None:
    """ホットキー修飾キーをソフトに解放する（extended key フラグも考慮）。"""
    KEYEVENTF_EXTENDEDKEY = 0x0001
    # 汎用的に修飾キーを解放する
    VK_SHIFT = 0x10
    send_keys(
        _ki(VK_CONTROL, KEYEVENTF_KEYUP),
        _ki(VK_CONTROL, KEYEVENTF_KEYUP | KEYEVENTF_EXTENDEDKEY),
        _ki(VK_MENU,    KEYEVENTF_KEYUP),
        _ki(VK_MENU,    KEYEVENTF_KEYUP | KEYEVENTF_EXTENDEDKEY),
        _ki(VK_SHIFT,   KEYEVENTF_KEYUP),
        _ki(VK_SPACE,   KEYEVENTF_KEYUP),
    )

def send_ctrl_c() -> None:
    """Ctrl+C を SendInput で送信する。"""
    send_keys(
        _ki(VK_CONTROL),
        _ki(VK_C),
        _ki(VK_C,       KEYEVENTF_KEYUP),
        _ki(VK_CONTROL, KEYEVENTF_KEYUP),
    )


# ------------------------------------------------------------------ #
# クリップボードのテキストを取得（スレッドセーフ）
# ------------------------------------------------------------------ #
CF_UNICODETEXT = 13

def get_clipboard_text() -> str:
    if not _user32.OpenClipboard(0):
        print(f"[PopAI] OpenClipboard 失敗 err={ctypes.get_last_error()}")
        return ""
    try:
        handle = _user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            print("[PopAI] GetClipboardData 失敗（テキスト形式なし）")
            return ""
        ptr = _kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            _kernel32.GlobalUnlock(ptr)
    except Exception as e:
        print(f"[PopAI] クリップボード取得エラー: {e}")
        return ""
    finally:
        _user32.CloseClipboard()


# ------------------------------------------------------------------ #
# ホットキー監視スレッド
# ------------------------------------------------------------------ #
class HotkeyThread(QThread):
    clipboard_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_keys: set = set()
        self._triggered        = False
        self._prev_hwnd        = 0
        self._keys_released    = threading.Event()

    @staticmethod
    def _normalize(key):
        mapping = {
            pynput_kb.Key.ctrl_l:  pynput_kb.Key.ctrl,
            pynput_kb.Key.ctrl_r:  pynput_kb.Key.ctrl,
            pynput_kb.Key.alt_l:   pynput_kb.Key.alt,
            pynput_kb.Key.alt_r:   pynput_kb.Key.alt,
            pynput_kb.Key.shift_l: pynput_kb.Key.shift,
            pynput_kb.Key.shift_r: pynput_kb.Key.shift,
            pynput_kb.Key.cmd_l:   pynput_kb.Key.cmd,
            pynput_kb.Key.cmd_r:   pynput_kb.Key.cmd,
        }
        return mapping.get(key, key)

    def _get_normalized_key(self, key):
        """pynput のキー入力から、正規化されたキーオブジェクトを取得する"""
        # Ctrlが押された際の文字キーは char が制御文字（\x01 など）になるため、
        # vk（仮想キーコード）を優先してアルファベット・数字を判定する
        if hasattr(key, 'vk') and key.vk is not None:
            vk = key.vk
            # A-Z (65-90) または 0-9 (48-57) の場合は vk から文字化
            if (65 <= vk <= 90) or (48 <= vk <= 57):
                return pynput_kb.KeyCode.from_char(chr(vk).lower())

        if hasattr(key, 'char') and key.char is not None:
            return pynput_kb.KeyCode.from_char(key.char.lower())

        return self._normalize(key)

    def _on_press(self, key):
        normalized = self._get_normalized_key(key)

        if normalized in (pynput_kb.Key.ctrl, pynput_kb.Key.alt, pynput_kb.Key.shift):
            hwnd = _user32.GetForegroundWindow()
            if hwnd:
                self._prev_hwnd = hwnd

        self._current_keys.add(normalized)

        # すべての修飾キーとトリガーキーが押されているか判定する
        if HOTKEY_NORMALIZED.issubset(self._current_keys) and not self._triggered:
            self._triggered = True
            self._keys_released.clear()
            print(f"[PopAI] ホットキー検出！HWND={self._prev_hwnd:#010x}, INPUT size={_sizeof_INPUT}")
            threading.Thread(target=self._fetch_clipboard, daemon=True).start()

    def _on_release(self, key):
        normalized = self._get_normalized_key(key)

        self._current_keys.discard(normalized)

        if normalized in HOTKEY_NORMALIZED:
            self._triggered = False

        if not (self._current_keys & HOTKEY_MODIFIERS):
            self._keys_released.set()

    def _fetch_clipboard(self):
        # 全キーが解放されるまで待つ（最大 0.5 秒に変更してレスポンス向上）
        self._keys_released.wait(timeout=0.5)

        # ホットキーの残留キーをソフト解放
        release_hotkey_keys()

        # 前のウィンドウへフォーカスを戻す
        if self._prev_hwnd:
            _user32.SetForegroundWindow(self._prev_hwnd)
            time.sleep(0.05)

        # Ctrl+C 送信
        send_ctrl_c()
        time.sleep(0.1)   # コピー完了を待つ

        text = get_clipboard_text()

        # 不要なログは出さず、メタデータのみ出力 (メモリのガイドラインに従う)
        print(f"[PopAI] 取得テキスト ({len(text)} 文字)")
        self.clipboard_ready.emit(text)

    def run(self):
        print(f"[PopAI] ホットキー監視スレッド開始 ({HOTKEY_STRING}) INPUT_SIZE={_sizeof_INPUT}")
        with pynput_kb.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            listener.join()
