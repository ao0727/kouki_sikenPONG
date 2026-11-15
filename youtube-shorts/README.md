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

## 処理の流れ（予定）

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
