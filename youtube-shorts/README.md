# YouTube ショート制作パイプライン

合成音声（VOICEVOX / VOICEROID）を使った縦型ショート動画（1080×1920, 60秒以内）を
台本から自動生成するための作業ディレクトリ。

## ディレクトリ構成

| パス | 内容 | Git管理 |
|---|---|---|
| `scripts/` | 台本ファイル（1本 = 1ファイル） | ○ |
| `src/` | 音声合成・字幕・動画組み立てのPythonコード | ○ |
| `assets/characters/` | キャラ立ち絵 | ○ |
| `assets/backgrounds/` | 背景画像・動画 | ○ |
| `assets/bgm/` | BGM（商用利用可のもののみ） | ○ |
| `assets/se/` | 効果音（商用利用可のもののみ） | ○ |
| `assets/fonts/` | 字幕用フォント | ○ |
| `build/audio/` | 合成した音声（中間生成物） | × |
| `build/video/` | 中間動画 | × |
| `output/` | 完成した mp4 | × |

## 使い方（Windows）

1. [VOICEVOX](https://voicevox.hiroshiba.jp/) をインストールして起動しておく
2. Python 3.10 以上をインストール
3. `make_short.bat scripts\001_flamingo.yaml` を実行（初回は自動でライブラリを入れる）
4. `output\001_flamingo.mp4` と `output\001_flamingo_投稿用.txt` ができる

- VOICEVOX 無しで動作確認だけしたいとき: `make_short.bat scripts\001_flamingo.yaml --dummy-tts`
- 立ち絵: `assets/characters/zundamon.png`, `metan.png`（透過PNG）を置くと丸の代わりに表示
- 背景: `assets/backgrounds/` に png/jpg を置くと使用
- BGM: `assets/bgm/` に mp3/wav を置くと音量12%で自動ミックス
- 台本のタイトルは `\n` で改行位置を指定できる

## 処理の流れ

1. `scripts/` に台本を書く
2. VOICEVOX エンジンでセリフごとに音声を生成 → `build/audio/`
   - VOICEROID を使う場合は手元のPCで書き出した wav を `build/audio/` に置く
3. 音声の長さに合わせて字幕・立ち絵・背景・BGMを合成 → `output/*.mp4`
4. タイトル・説明欄・ハッシュタグ・クレジットを出力

## 注意（収益化）

- VOICEVOX はキャラごとにクレジット表記が必要（例: `VOICEVOX:ずんだもん`）
- 素材はすべて商用利用可のものを使う
- テンプレの大量生産は YouTube の「inauthentic content」ポリシーで収益化対象外になりやすい。
  独自の切り口・編集を入れること
