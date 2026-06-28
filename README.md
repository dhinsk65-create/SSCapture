# SS Capture

**ホットキー・クリップボード監視で、3つの保存方法をまとめて管理するシンプルキャプチャツール**

![version](https://img.shields.io/badge/version-v1.0-blue)
![platform](https://img.shields.io/badge/platform-Windows-lightgrey)

---

## できること

| 機能 | 説明 |
|------|------|
| **アクティブウィンドウ保存** | 設定したホットキーで前面にあるウィンドウをキャプチャ |
| **全画面保存** | 別ホットキーで全デスクトップをキャプチャ（マルチモニター対応） |
| **クリップボード監視** | Win+Shift+S などで取った範囲画像を自動的にファイル保存 |
| **クリップボード連動** | キャプチャと同時にクリップボードにも画像を送れる |
| **保存先フォルダ設定** | 任意のフォルダを指定、日付ごとのサブフォルダを自動作成・設定は次回も引き継ぎ |
| **シャッター音** | 保存時にカシャッと鳴る（ON/OFF切り替え可） |
| **スタートアップ登録** | Windows 起動時に自動スタート |
| **トレイ格納** | ×ボタンでトレイに格納、常駐して邪魔にならない |

---

## 使い方

### 基本

1. `SSCapture.exe` を起動
2. ホットキーを押す、または Win+Shift+S で範囲選択する
3. 設定したフォルダ / 日付 / 連番.png に自動保存される

### ホットキー

| ホットキー | デフォルト | 動作 |
|-----------|-----------|------|
| アクティブウィンドウ | `Print Screen` | 前面ウィンドウをキャプチャ |
| 全画面 | `Shift + Print Screen` | 全画面をキャプチャ |

「変更…」ボタンで任意のキー（Ctrl+F9 など組み合わせも可）に変更できます。

### クリップボード監視

「クリップボードの画像を自動保存する」をONにすると、  
`Win+Shift+S` で範囲指定したスクリーンショットも自動的にファイル保存されます。

---

## 保存先

```
ピクチャ\SSCapture\          ← デフォルト（変更可・設定は次回も引き継ぎ）
  └── 20260628\
        ├── 0001.png
        ├── 0002.png
        └── ...
```

アプリ内の「開く」ボタンで保存先フォルダを直接開けます。

---

## インストール

Python 不要。`SSCapture.exe` を好きな場所に置いて起動するだけです。

---

## ビルド方法（開発者向け）

```bash
# 依存ライブラリ
pip install pillow keyboard pystray pywin32

# アイコン生成
python src/create_icon.py

# EXEビルド
pyinstaller SSCapture.spec --noconfirm
```

---

## 作者

**ふぁん × Claude Code**

- X: [@f_temproll](https://x.com/f_temproll)
- NOTE: [https://note.com/fun_temproll](https://note.com/fun_temproll)
