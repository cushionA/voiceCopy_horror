# ChatterBox Zero-shot Voice Conversion 検証

**ファイル**: `vc_test_chatterbox.json`
**目的**: 事前学習なしで「ある声 → 別の声」に変換できるか確認する PoC
**作成日**: 2026-05-05（v3: ChatterBox Official 23-Lang v2 に切替、日本語ネイティブ対応）

## 使用モデル

| 項目 | 値 |
|------|-----|
| Engine | `ChatterBoxOfficial23LangEngineNode` (model_version=v2) |
| HF repo | `ResembleAI/chatterbox` の **23-Lang** ブランチ |
| ファイル | `t3_mtl23ls_v2.safetensors`, `s3gen.safetensors`, `ve.safetensors`, `conds.pt` |
| 配置 | `ComfyUI/models/TTS/chatterbox_official_23lang/Official 23-Lang/` |
| Language 設定 | Japanese |
| 訓練データ | 23 言語マルチリンガル（日本語含む） |
| ライセンス | MIT |

**過去版 (v2 まで)**: 英語のみ訓練の `ChatterBoxEngineNode` (`ResembleAI/chatterbox`) を使用していた。日本語 source / target で voice encoder の精度が頭打ちになっていた可能性があり、23-Lang 版に切替。
**関連スパイク**: [docs/reports/spikes/2026-05-05_qwen3-tts-onnx-feasibility.md](../docs/reports/spikes/2026-05-05_qwen3-tts-onnx-feasibility.md)

---

## なぜ ChatterBox を試すのか

- Sentis 路線の本命候補は **OpenVoice v2** だったが、TTS-Audio-Suite には未統合
- **ChatterBox の `UnifiedVoiceChangerNode` が zero-shot VC を提供**（事前学習不要、2 つの音声を繋ぐだけ）
- 既存 ComfyUI 環境で即検証可能 → 最小ステップで「VC というアプローチが voice_horror に通用するか」を判定できる

OpenVoice v2 の本格検証は本 PoC の結果次第。VC 自体の実用性が確認できれば次に OpenVoice v2 を ComfyUI 統合 or 直接 Python で動かす。

---

## 「target voice の特徴を誇張する」2 つの方法

VC 出力で target の声色がもっと反映されてほしい場合、以下 2 アプローチがある:

### 方法 1: refinement_passes を増やす（本 workflow で検証）

`UnifiedVoiceChangerNode` の `refinement_passes` (1-30, 推奨 max 5) を増やすと、各 pass で出力を再度 VC にかけて target に寄せていく。

| passes | 効果 | リスク |
|--------|------|------|
| 1 | basic VC、source の特徴も多く残る | 似てない感 |
| 3 | 中程度の target 寄せ | バランス良い |
| 5 | 強誇張、target 色濃く | 歪み・破綻が出る可能性 |
| 10+ | 推奨外 | 大きく破綻する |

本 workflow は 1 / 3 / 5 を並列実行して聴き比べられる。

### 方法 2: source 音声を「無個性」にする

source の声色特徴が薄いほど target に置き換わる余地が増える。具体策:

| 手段 | 設定 | 出力例 |
|------|------|--------|
| **VOICEVOX** 中性キャラ | 「中部つるぎ」「ずんだもん あまあま」を**抑揚下げ**で合成 | 平坦な日本語 |
| **VOICEVOX ささやき** | 「四国めたん ささやき」「九州そら ささやき」 | 抑揚弱め+息混じり、ホラー演出にも転用可 |
| **モノトーン朗読** | 自分で「あ・え・い・お・う」を一定ピッチで30秒朗読 | 完全無個性、声質テスト用 |
| **Qwen3-TTS** 既存 workflow | プリセット voice なしで温度 0.5 程度に下げて生成 | 抑揚抑えた合成音声 |

→ 生成した無個性 source を `neutral_source.wav` として `ComfyUI/input/` に配置し、本 workflow の `LoadAudio` のファイル名を切り替えて再実行すれば比較可能。

---

## 事前準備

### 必要ファイル

| ファイル | 配置先 | 取得方法 |
|---------|-------|---------|
| `my_sampleVoice.wav` | `ComfyUI/input/` | 既存（北風と太陽、自分の声） |
| **`girl_jp.wav`** ★要作成 | `ComfyUI/input/` | VOICEVOX 等で少女声 20-30 秒生成 |
| `female_01.wav` (任意) | `ComfyUI/input/` | TTS-Audio-Suite 同梱（英語女性、配置済） |

### `girl_jp.wav` の作り方

VOICEVOX で以下のテキストを合成:

```
ねえ、聞こえる？私の声、ちゃんと届いてる？
よかった。ずっとひとりだったから、誰かと話せて嬉しい。
この家ね、本当は危ないの。気をつけて。
マギーとアルフレッド、それからマークス。三人いるから。
彼らに見つかったら、すぐに隠れて。
クローゼットでも、机の下でも、どこでもいいから。
私はずっとあなたを見てる。
困ったら、電話して。すぐに行くから。
```

推奨キャラ: `冥鳴ひまり ノーマル` / `春日部つむぎ ノーマル` / `九州そら ささやき`

書き出した WAV を `girl_jp.wav` として `C:/Users/tatuk/Documents/ComfyUI/input/` に配置。

---

## 使い方

1. ComfyUI を起動
2. `Load` → `vc_test_chatterbox.json`
3. 上部の `Queue Prompt` を実行
4. 4 つの PreviewAudio で結果を再生（passes=1, 3, 5, 本命方向）
5. `ComfyUI/output/vh_vc_*.wav` にも保存される

---

## 4 行の検証構成

| 行 | source（内容を保持） | target（声色を取得） | passes | 出力ファイル |
|----|------------------|------------------|--------|-------------|
| 1 | my_sampleVoice (自分・日本語) | girl_jp (少女・日本語) | 1 | vh_vc_my2girl_p1.wav |
| 2 | 同上 | 同上 | 3 | vh_vc_my2girl_p3.wav |
| 3 | 同上 | 同上 | 5 | vh_vc_my2girl_p5.wav |
| 4 ★ | girl_jp (少女・日本語) | my_sampleVoice (自分) | 3 | vh_vc_girl2my_p3.wav |

**行 4 が voice_horror 本命**: 「少女のセリフがプレイヤー声色に変換される」構図そのもの。

---

## 結果の評価

### 必須評価（4 行それぞれ）

| 項目 | 評価 | メモ |
|------|------|------|
| 声色の類似度（耳） | ◎/○/△/× | |
| 内容（言語・抑揚）の保持 | ◎/○/△/× | |
| ノイズ・歪みの有無 | 少/中/多 | |
| 推論時間 | 秒 | passes 倍数で増える想定 |
| VRAM 使用量 | GB | |

### 比較ポイント

- **passes=1 → 5 の差**: 誇張効果が顕著か、それとも飽和するか
- **歪みの境界**: passes=5 で破綻するなら 3 が実用ライン
- **行 4 の品質**: voice_horror 本命構図で「自分の声」と認識できるか

### 次のステップ判定

| 結果 | 次のアクション |
|------|--------------|
| ◎ passes=3 〜 5 で行 4 が十分な品質 | OpenVoice v2 検証スキップ → ChatterBox VC を Unity 組込検討 |
| ○ そこそこ似てるが品質改善余地あり | 「無個性 source」を追加検証 → 改善するか確認 |
| △ 一定の声色寄せはあるが似てない | OpenVoice v2 を Python で直接動かして比較 |
| × 全然似てない / 破綻 | VC 路線自体を再考、TTS 路線に戻すか検討 |

---

## トラブルシューティング

### `girl_jp.wav` が見つからない
- VOICEVOX で生成してファイル名を `girl_jp.wav` にして `ComfyUI/input/` に配置
- ComfyUI の R キーでキャッシュ更新
- それでも認識しないなら ComfyUI 再起動

### ChatterBox エンジンが DL に失敗する
- `ComfyUI/models/TTS/chatterbox/` を一度削除してリトライ
- 公式 HF リポジトリへのアクセス可否を確認

### passes=5 でクラッシュ / OOM
- `max_chunk_duration` を 30 → 15 に下げて `chunk_method=smart` のまま
- VRAM 8GB の場合は同時実行を避ける（1 つずつ Queue する）

### 出力にノイズ・破綻が多い
- source 音声を 25 秒以下にトリミング
- 22.05/24/44.1 kHz / mono / 16-bit に正規化
- VOICEVOX 出力はデフォルトで 24kHz mono なので変換不要

### 日本語が「Konnitiwa」化する
- ChatterBox は本来英語モデル。VC モードでは内容（音響特徴）を保持するだけなので原理上は崩れないはずだが、内部で text-conditioning が混入している可能性あり
- 結果が破綻する場合: ChatterBox VC は voice_horror 用途には不向き → OpenVoice v2 へ移行

---

## 関連ファイル

- `vc_test_chatterbox.json` — 本 workflow
- `japanese_clone_test_qwen3.json` — 既存の Qwen3 voice cloning workflow（比較用）
- `my_sampleVoice.wav` — 自分の声（ボイスクローン基準）
- `docs/reports/spikes/2026-05-05_qwen3-tts-onnx-feasibility.md` — Qwen3 ONNX スパイク結果

## 参照

- [TTS-Audio-Suite Voice Changer 例](file:///C:/Users/tatuk/Documents/ComfyUI/custom_nodes/TTS-Audio-Suite/example_workflows/Unified%20%F0%9F%94%84%20Voice%20Changer%20-%20RVC%20X%20ChatterBox.json) — 本 workflow のベース
- [ChatterBox 公式](https://github.com/resemble-ai/chatterbox) — モデル本体（MIT）
- [VOICEVOX](https://voicevox.hiroshiba.jp/) — 無個性 / 少女声 source 生成用
