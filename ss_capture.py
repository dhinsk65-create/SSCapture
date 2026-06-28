"""
ss_capture.py  v1.0
アクティブウィンドウ／全画面スクリーンショットをホットキーで保存するツール

作者  : ふぁん × Claude Code
X     : @f_temproll
NOTE  : https://note.com/fun_temproll

保存先: <設定フォルダ>/YYYYMMDD/0001.png, 0002.png ...
"""

import sys
import os
import io
import json
import wave
import array
import math
import random
import winsound
import threading
import winreg
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import tempfile
import keyboard
import pystray
import win32clipboard
import ctypes
import ctypes.wintypes
import win32con
import win32api
from PIL import ImageGrab, Image, ImageDraw
import win32gui
import win32process

# ---------------------------------------------------------------
APP_NAME       = "SS Capture"
APP_VERSION    = "v1.0"
AUTHOR         = "ふぁん × Claude Code"
AUTHOR_X       = "@f_temproll"
AUTHOR_NOTE    = "https://note.com/fun_temproll"

DEFAULT_SAVE_ROOT   = Path.home() / "Pictures" / "SSCapture"
DEFAULT_HOTKEY_WIN  = "print screen"          # アクティブウィンドウ
DEFAULT_HOTKEY_FULL = "left shift+print screen"  # 全画面
STARTUP_NAME        = "SSCapture"
CONFIG_PATH         = Path.home() / "AppData" / "Local" / "SSCapture" / "config.json"
# ---------------------------------------------------------------


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_exe_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(__file__)


def get_save_folder(root: Path) -> Path:
    folder = root / datetime.now().strftime("%Y%m%d")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def next_index(folder: Path) -> int:
    nums = []
    for f in folder.glob("*.png"):
        try:
            nums.append(int(f.stem))
        except ValueError:
            pass
    return max(nums) + 1 if nums else 1


def _get_window_rect_no_shadow(hwnd: int) -> tuple[int, int, int, int]:
    """ドロップシャドウを除いた実際のウィンドウ領域を返す"""
    try:
        rect = ctypes.wintypes.RECT()
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(rect), ctypes.sizeof(rect))
        return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return win32gui.GetWindowRect(hwnd)


def capture_hwnd(hwnd: int | None, save_root: Path) -> tuple[str, Image.Image, Path] | None:
    if not hwnd:
        return None
    title = win32gui.GetWindowText(hwnd)
    l, t, r, b = _get_window_rect_no_shadow(hwnd)
    if r - l < 10 or b - t < 10:
        return None
    img = ImageGrab.grab(bbox=(l, t, r, b), all_screens=True)
    folder = get_save_folder(save_root)
    path = folder / f"{next_index(folder):04d}.png"
    img.save(path)
    return title, img, path


def capture_fullscreen(save_root: Path) -> tuple[str, Image.Image, Path] | None:
    img = ImageGrab.grab(all_screens=True)
    folder = get_save_folder(save_root)
    path = folder / f"{next_index(folder):04d}.png"
    img.save(path)
    return "全画面", img, path


def copy_to_clipboard(img: Image.Image):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "BMP")
    data = buf.getvalue()[14:]
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()


# ---- スタートアップ -------------------------------------------
def _startup_reg():
    return winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
    )

def is_startup_registered() -> bool:
    try:
        k = _startup_reg()
        winreg.QueryValueEx(k, STARTUP_NAME)
        winreg.CloseKey(k)
        return True
    except Exception:
        return False

def set_startup(enable: bool):
    k = _startup_reg()
    if enable:
        winreg.SetValueEx(k, STARTUP_NAME, 0, winreg.REG_SZ, get_exe_path())
    else:
        try:
            winreg.DeleteValue(k, STARTUP_NAME)
        except FileNotFoundError:
            pass
    winreg.CloseKey(k)


# ---- アイコン生成 ---------------------------------------------
def _make_camera_icon(color: str) -> Image.Image:
    """指定色のカメラアイコンをPILで生成"""
    s = 64
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, 60, 60], radius=12, fill=color)
    d.rounded_rectangle([8, 20, 56, 54], radius=5, fill="white")
    cx, cy, cr = 32, 37, 11
    d.ellipse([cx-cr, cy-cr, cx+cr, cy+cr], fill=color)
    ir = cr * 0.65
    d.ellipse([cx-ir, cy-ir, cx+ir, cy+ir], fill="white")
    pr = ir * 0.45
    d.ellipse([cx-pr, cy-pr, cx+pr, cy+pr], fill=color)
    d.rounded_rectangle([20, 13, 34, 22], radius=3, fill="white")
    d.ellipse([43, 13, 51, 21], fill="white")
    return img

def _make_tray_icon() -> Image.Image:
    return _make_camera_icon("#2d7dd2")


def _make_shutter_wav() -> bytes:
    """カシャッというシャッター音のWAVバイト列を生成"""
    rate = 44100
    buf = io.BytesIO()
    data = array.array('h')

    # 前半：高周波クリック（シャッター開）約25ms
    click_len = int(rate * 0.025)
    for i in range(click_len):
        t = i / click_len
        env = math.exp(-t * 18)
        val = int(32767 * env * (
            math.sin(2 * math.pi * 1800 * i / rate) * 0.6 +
            (random.random() * 2 - 1) * 0.4))
        data.append(max(-32767, min(32767, val)))

    # 後半：低めのノイズ減衰（シャッター閉）約40ms
    noise_len = int(rate * 0.040)
    for i in range(noise_len):
        t = i / noise_len
        env = math.exp(-t * 25)
        val = int(32767 * env * (random.random() * 2 - 1) * 0.5)
        data.append(max(-32767, min(32767, val)))

    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())
    return buf.getvalue()


_SHUTTER_WAV = _make_shutter_wav()


def play_shutter():
    winsound.PlaySound(_SHUTTER_WAV, winsound.SND_MEMORY)


# ===============================================================
# ホットキー入力キャプチャ（修飾キー対応）
# ===============================================================
MODIFIERS = {"ctrl", "left ctrl", "right ctrl",
             "shift", "left shift", "right shift",
             "alt", "left alt", "right alt",
             "windows", "left windows", "right windows"}

MODIFIER_CANONICAL = {
    "left ctrl": "ctrl", "right ctrl": "ctrl",
    "left shift": "shift", "right shift": "shift",
    "left alt": "alt", "right alt": "alt",
    "left windows": "windows", "right windows": "windows",
}

def capture_hotkey_combo() -> str:
    """
    押されたキーを読み取り 'ctrl+shift+f9' 形式で返す。
    修飾キーだけで終わった場合はそのキー名を返す。
    """
    held_mods: list[str] = []
    while True:
        event = keyboard.read_event(suppress=False)
        if event.event_type != "down":
            continue
        name = event.name.lower()
        canonical = MODIFIER_CANONICAL.get(name, name)

        if canonical in MODIFIERS or name in MODIFIERS:
            # 修飾キー → 蓄積して次を待つ
            mod = MODIFIER_CANONICAL.get(name, canonical)
            if mod not in held_mods:
                held_mods.append(mod)
        else:
            # 通常キー → 修飾キーと組み合わせて返す
            parts = held_mods + [name]
            return "+".join(parts)


# ===============================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.resizable(False, False)

        self._cfg         = load_config()
        self._save_root   = Path(self._cfg.get("save_root", str(DEFAULT_SAVE_ROOT)))
        self._hotkey_win  = self._cfg.get("hotkey_win",  DEFAULT_HOTKEY_WIN)
        self._hotkey_full = self._cfg.get("hotkey_full", DEFAULT_HOTKEY_FULL)
        self._hook_win    = None
        self._hook_full   = None
        self._count       = 0
        self._last_hwnd   = None
        self._own_pid     = os.getpid()
        self._tray: pystray.Icon | None = None
        self._cb_seq      = win32clipboard.GetClipboardSequenceNumber()
        self._cb_polling  = False

        self._build_ui()
        self._register_hotkeys()
        self._track_active_window()
        self._start_tray()
        self.protocol("WM_DELETE_WINDOW", self._to_tray)

        # タスクバーアイコン設定
        ico = self._save_tmp_ico(_make_camera_icon("#2d7dd2"))
        self.iconbitmap(ico)

    # ---- UI -------------------------------------------------------
    def _build_ui(self):
        PAD = 12

        # ---- ホットキー設定 ----------------------------------------
        hk_frame = ttk.LabelFrame(self, text="ホットキー設定", padding=PAD)
        hk_frame.grid(row=0, column=0, padx=PAD, pady=(PAD, 4), sticky="ew")

        # アクティブウィンドウ
        ttk.Label(hk_frame, text="アクティブウィンドウ:").grid(
            row=0, column=0, sticky="w")
        self._hk_win_label = ttk.Label(
            hk_frame, text=self._hotkey_win.upper(),
            font=("Consolas", 11, "bold"), width=22,
            anchor="center", relief="groove", padding=4)
        self._hk_win_label.grid(row=0, column=1, padx=6)
        self._set_win_btn = ttk.Button(
            hk_frame, text="変更…", width=8,
            command=lambda: self._start_key_capture("win"))
        self._set_win_btn.grid(row=0, column=2)

        # 全画面
        ttk.Label(hk_frame, text="全画面:").grid(
            row=1, column=0, sticky="w", pady=(6, 0))
        self._hk_full_label = ttk.Label(
            hk_frame, text=self._hotkey_full.upper(),
            font=("Consolas", 11, "bold"), width=22,
            anchor="center", relief="groove", padding=4)
        self._hk_full_label.grid(row=1, column=1, padx=6, pady=(6, 0))
        self._set_full_btn = ttk.Button(
            hk_frame, text="変更…", width=8,
            command=lambda: self._start_key_capture("full"))
        self._set_full_btn.grid(row=1, column=2, pady=(6, 0))

        self._hk_hint = ttk.Label(hk_frame, text="", foreground="#e67e00")
        self._hk_hint.grid(row=2, column=0, columnspan=3, pady=(6, 0))

        # suppress / クリップボード
        self._suppress_var = tk.BooleanVar(value=self._cfg.get("suppress", False))
        ttk.Checkbutton(
            hk_frame, variable=self._suppress_var,
            text="他のアプリにキーを渡さない（suppress）",
            command=self._on_suppress_change,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self._clipboard_var = tk.BooleanVar(value=self._cfg.get("clipboard", True))
        ttk.Checkbutton(
            hk_frame, variable=self._clipboard_var,
            text="クリップボードにもコピーする",
            command=self._save_config,
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(2, 0))

        self._sound_var = tk.BooleanVar(value=self._cfg.get("sound", True))
        ttk.Checkbutton(
            hk_frame, variable=self._sound_var,
            text="シャッター音を鳴らす",
            command=self._save_config,
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(2, 0))

        # ---- クリップボード監視 ------------------------------------
        cb_frame = ttk.LabelFrame(self, text="クリップボード監視", padding=PAD)
        cb_frame.grid(row=1, column=0, padx=PAD, pady=4, sticky="ew")

        self._watch_cb_var = tk.BooleanVar(value=self._cfg.get("watch_cb", False))
        ttk.Checkbutton(
            cb_frame, variable=self._watch_cb_var,
            text="クリップボードの画像を自動保存する",
            command=self._on_watch_cb_change,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(cb_frame,
                  text="Win+Shift+S など外部ツールの画像も対象",
                  foreground="gray").grid(row=1, column=0, sticky="w", pady=(2, 0))

        # ---- 保存先 ------------------------------------------------
        save_frame = ttk.LabelFrame(self, text="保存先フォルダ", padding=(PAD, 6))
        save_frame.grid(row=2, column=0, padx=PAD, pady=4, sticky="ew")

        self._folder_label = ttk.Label(
            save_frame, text=str(self._save_root),
            foreground="gray", wraplength=320)
        self._folder_label.grid(row=0, column=0, sticky="w")

        btn_sf = ttk.Frame(save_frame)
        btn_sf.grid(row=0, column=1, padx=(8, 0))
        ttk.Button(btn_sf, text="変更", command=self._browse_save_root,
                   width=6).grid(row=0, column=0, pady=(0, 2))
        ttk.Button(btn_sf, text="開く", command=self._open_folder,
                   width=6).grid(row=1, column=0)

        # ---- スタートアップ ----------------------------------------
        su_frame = ttk.LabelFrame(self, text="スタートアップ", padding=(PAD, 6))
        su_frame.grid(row=3, column=0, padx=PAD, pady=4, sticky="ew")

        self._startup_var = tk.BooleanVar(value=is_startup_registered())
        ttk.Checkbutton(
            su_frame, variable=self._startup_var,
            text="Windows 起動時に自動スタート",
            command=self._on_startup_change,
        ).grid(row=0, column=0, sticky="w")

        self._startup_lbl = ttk.Label(
            su_frame,
            text="登録済み" if is_startup_registered() else "未登録",
            foreground="#28a745" if is_startup_registered() else "gray")
        self._startup_lbl.grid(row=0, column=1, padx=(12, 0))

        # ---- ステータス / ログ -------------------------------------
        self._status = ttk.Label(self, text="保存: 0 枚", foreground="gray")
        self._status.grid(row=4, column=0, padx=PAD, pady=(4, 0))

        log_frame = ttk.LabelFrame(self, text="ログ", padding=(PAD, 4))
        log_frame.grid(row=5, column=0, padx=PAD, pady=(4, 0), sticky="ew")

        self._log = tk.Text(log_frame, width=50, height=7,
                            state="disabled", font=("Consolas", 9))
        sb = ttk.Scrollbar(log_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        self._log.grid(row=0, column=0)
        sb.grid(row=0, column=1, sticky="ns")

        # ---- 下部ボタン --------------------------------------------
        bot_frame = ttk.Frame(self)
        bot_frame.grid(row=6, column=0, padx=PAD, pady=(4, PAD))
        ttk.Button(bot_frame, text="トレイに格納",
                   command=self._to_tray, width=14).grid(row=0, column=0, padx=4)
        ttk.Button(bot_frame, text="About",
                   command=self._show_about, width=10).grid(row=0, column=1, padx=4)

    # ---- ホットキー -----------------------------------------------
    def _register_hotkeys(self):
        suppress = self._suppress_var.get() if hasattr(self, "_suppress_var") else False
        for hook_attr in ("_hook_win", "_hook_full"):
            h = getattr(self, hook_attr, None)
            if h:
                try:
                    keyboard.remove_hotkey(h)
                except Exception:
                    pass
        self._hook_win = keyboard.add_hotkey(
            self._hotkey_win, self._do_capture_win, suppress=suppress)
        self._hook_full = keyboard.add_hotkey(
            self._hotkey_full, self._do_capture_full, suppress=suppress)

    def _on_suppress_change(self):
        self._register_hotkeys()
        self._save_config()
        self._log_write("suppress " + ("ON" if self._suppress_var.get() else "OFF"))

    def _start_key_capture(self, target: str):
        """target: 'win' or 'full'"""
        self._set_win_btn.configure(state="disabled")
        self._set_full_btn.configure(state="disabled")
        label = "アクティブウィンドウ" if target == "win" else "全画面"
        self._hk_hint.configure(text=f"[{label}] キーを押してください（組み合わせも可）…")
        lbl = self._hk_win_label if target == "win" else self._hk_full_label
        lbl.configure(text="？")
        threading.Thread(
            target=self._wait_for_key, args=(target,), daemon=True).start()

    def _wait_for_key(self, target: str):
        combo = capture_hotkey_combo()
        self.after(0, lambda: self._apply_new_key(target, combo))

    def _apply_new_key(self, target: str, combo: str):
        self._hk_hint.configure(text="")
        self._set_win_btn.configure(state="normal")
        self._set_full_btn.configure(state="normal")
        if target == "win":
            self._hotkey_win = combo
            self._hk_win_label.configure(text=combo.upper())
        else:
            self._hotkey_full = combo
            self._hk_full_label.configure(text=combo.upper())
        self._register_hotkeys()
        self._save_config()
        label = "アクティブウィンドウ" if target == "win" else "全画面"
        self._log_write(f"[{label}] ホットキー → [{combo.upper()}]")

    # ---- クリップボード監視 ----------------------------------------
    def _on_watch_cb_change(self):
        if self._watch_cb_var.get():
            self._cb_seq = win32clipboard.GetClipboardSequenceNumber()
            if not self._cb_polling:
                self._cb_polling = True
                self._poll_clipboard()
            self._log_write("クリップボード監視 開始")
        else:
            self._cb_polling = False
            self._log_write("クリップボード監視 停止")
        self._save_config()

    def _poll_clipboard(self):
        if not self._cb_polling:
            return
        seq = win32clipboard.GetClipboardSequenceNumber()
        if seq != self._cb_seq:
            self._cb_seq = seq
            self._save_clipboard_image()
        self.after(300, self._poll_clipboard)

    def _save_clipboard_image(self):
        try:
            img = ImageGrab.grabclipboard()
        except Exception:
            return
        # Windows 11 Snipping Tool はファイルパスのリストを返すことがある
        if isinstance(img, list):
            for item in img:
                p = Path(str(item))
                if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
                    try:
                        img = Image.open(p)
                        break
                    except Exception:
                        pass
            else:
                return
        if not isinstance(img, Image.Image):
            return
        folder = get_save_folder(self._save_root)
        path = folder / f"{next_index(folder):04d}.png"
        img.save(path)
        self._count += 1
        self.after(0, lambda: self._update_ui(path, "クリップボード", ""))

    # ---- スタートアップ --------------------------------------------
    def _on_startup_change(self):
        enable = self._startup_var.get()
        try:
            set_startup(enable)
            self._startup_lbl.configure(
                text="登録済み" if enable else "未登録",
                foreground="#28a745" if enable else "gray")
            self._log_write("スタートアップ " + ("登録" if enable else "解除"))
        except Exception as e:
            self._startup_var.set(not enable)
            self._log_write(f"スタートアップ変更失敗: {e}")

    # ---- アクティブウィンドウ追跡 ----------------------------------
    def _track_active_window(self):
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            try:
                if win32process.GetWindowThreadProcessId(hwnd)[1] != self._own_pid:
                    self._last_hwnd = hwnd
            except Exception:
                pass
        self.after(100, self._track_active_window)

    # ---- キャプチャ ------------------------------------------------
    def _resolve_hwnd(self) -> int | None:
        return win32gui.GetForegroundWindow()

    def _do_capture_win(self):
        result = capture_hwnd(self._resolve_hwnd(), self._save_root)
        self._finish_capture(result)

    def _do_capture_full(self):
        result = capture_fullscreen(self._save_root)
        self._finish_capture(result)

    def _finish_capture(self, result):
        if result is None:
            self.after(0, lambda: self._log_write("キャプチャ失敗"))
            return
        title, img, path = result
        self._count += 1
        suffix = ""
        if self._clipboard_var.get():
            try:
                copy_to_clipboard(img)
                self._cb_seq = win32clipboard.GetClipboardSequenceNumber()
                suffix = " + クリップボード"
            except Exception:
                pass
        self.after(0, lambda: self._update_ui(path, title, suffix))

    def _update_ui(self, path: Path, title: str, suffix: str):
        self._status.configure(text=f"保存: {self._count} 枚")
        self._log_write(f"{path.name}{suffix}  「{title}」")
        self._flash_status(path.name)
        if self._sound_var.get():
            threading.Thread(target=play_shutter, daemon=True).start()


    # ---- 保存先変更 ------------------------------------------------
    def _flash_status(self, filename: str):
        self._status.configure(
            text=f"✓ 保存: {self._count} 枚  [{filename}]",
            foreground="#28a745")
        self.after(1500, lambda: self._status.configure(
            text=f"保存: {self._count} 枚",
            foreground="gray"))

    def _save_config(self):
        save_config({
            "save_root":   str(self._save_root),
            "hotkey_win":  self._hotkey_win,
            "hotkey_full": self._hotkey_full,
            "suppress":    self._suppress_var.get(),
            "clipboard":   self._clipboard_var.get(),
            "sound":       self._sound_var.get(),
            "watch_cb":    self._watch_cb_var.get(),
        })

    def _browse_save_root(self):
        folder = filedialog.askdirectory(
            title="保存先フォルダを選択",
            initialdir=str(self._save_root))
        if folder:
            self._save_root = Path(folder)
            self._folder_label.configure(text=str(self._save_root))
            self._log_write(f"保存先 → {self._save_root}")
            self._save_config()

    def _open_folder(self):
        folder = get_save_folder(self._save_root)
        os.startfile(folder)

    # ---- ログ -------------------------------------------------------
    def _log_write(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.configure(state="normal")
        self._log.insert("end", f"[{ts}] {msg}\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    # ---- About ----------------------------------------------------
    def _show_about(self):
        win = tk.Toplevel(self)
        win.title(f"About {APP_NAME}")
        win.resizable(False, False)
        win.grab_set()

        PAD = 20
        # アイコン表示
        try:
            icon_path = Path(__file__).parent / "icon.ico"
            icon_img = Image.open(icon_path).resize((64, 64), Image.LANCZOS)
            self._about_icon = tk.PhotoImage(data=self._pil_to_photodata(icon_img))
            ttk.Label(win, image=self._about_icon).grid(
                row=0, column=0, padx=PAD, pady=(PAD, 4))
        except Exception:
            pass

        ttk.Label(win, text=APP_NAME,
                  font=("", 16, "bold")).grid(row=1, column=0, pady=(0, 2))
        ttk.Label(win, text=APP_VERSION,
                  foreground="gray").grid(row=2, column=0)
        ttk.Separator(win, orient="horizontal").grid(
            row=3, column=0, sticky="ew", padx=PAD, pady=10)
        ttk.Label(win, text=AUTHOR).grid(row=4, column=0)
        ttk.Label(win, text=f"X: {AUTHOR_X}",
                  foreground="#1d9bf0").grid(row=5, column=0, pady=(4, 0))
        ttk.Label(win, text=AUTHOR_NOTE,
                  foreground="#41b383").grid(row=6, column=0, pady=(2, 0))
        ttk.Separator(win, orient="horizontal").grid(
            row=7, column=0, sticky="ew", padx=PAD, pady=10)
        ttk.Label(win,
                  text="アクティブウィンドウ／全画面のSSを\nホットキー一発で保存するツール",
                  justify="center").grid(row=8, column=0)
        ttk.Button(win, text="閉じる", command=win.destroy, width=10).grid(
            row=9, column=0, pady=(PAD, PAD))

    @staticmethod
    def _save_tmp_ico(img: Image.Image) -> str:
        """PIL画像を一時.icoファイルに保存してパスを返す"""
        tmp = tempfile.NamedTemporaryFile(suffix=".ico", delete=False)
        tmp.close()
        img.resize((32, 32), Image.LANCZOS).save(tmp.name, format="ICO")
        return tmp.name

    @staticmethod
    def _pil_to_tk(img: Image.Image, size: int) -> tk.PhotoImage:
        img = img.resize((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        import base64
        return tk.PhotoImage(data=base64.b64encode(buf.getvalue()).decode())

    @staticmethod
    def _pil_to_photodata(img: Image.Image) -> str:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        import base64
        return base64.b64encode(buf.getvalue()).decode()

    # ---- トレイ ----------------------------------------------------
    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem(f"{APP_NAME} を開く", self._from_tray, default=True),
            pystray.MenuItem("終了", self._quit),
        )
        self._tray = pystray.Icon(
            "ss_capture", _make_tray_icon(), APP_NAME, menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _to_tray(self):
        self.withdraw()

    def _from_tray(self, icon=None, item=None):
        self.after(0, self.deiconify)

    # ---- 終了 -------------------------------------------------------
    def _quit(self, icon=None, item=None):
        for hook_attr in ("_hook_win", "_hook_full"):
            h = getattr(self, hook_attr, None)
            if h:
                try:
                    keyboard.remove_hotkey(h)
                except Exception:
                    pass
        if self._tray:
            self._tray.stop()
        self.after(0, self.destroy)


if __name__ == "__main__":
    app = App()
    app.mainloop()
