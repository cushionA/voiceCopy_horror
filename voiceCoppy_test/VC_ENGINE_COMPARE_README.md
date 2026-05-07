# VC エンジン 3 種並列比較 (ComfyUI 完結版)

**ファイル**: `vc_engine_compare.json`
**目的**: TTS-Audio-Suite で zero-shot VC をサポートする 3 エンジンを同じ入力で並列実行して品質を聴き比べる
**作成日**: 2026-05-05

---

## 設計思想（ユーザー指摘を反映）

> 「音→音の変換でいいなら Qwen 使う必要ないよね」 ← その通り

VC 路線では **TTS の言語モデル部分は完全にデッドウェイト**:
- TTS = テキスト → 音声 (LLM + acoustic + vocoder)
- VC = 音声 → 音声 (speaker encoder + content encoder + vocoder)
- LLM 部分（数百MB〜数GB）が VC では不要

→ Qwen3-TTS 1.7B (~10GB ONNX) や ElBruno 統合は VC 用途では over-spec。**純 VC エンジンに集中する**。

## 比較する 3 エンジン

| エンジン | 内部モデル | サイズ | 日本語 | ライセンス |
|---------|----------|--------|--------|----------|
| **ChatterBox 通常版** | `ResembleAI/chatterbox` | ~500MB | △ 非公式 | MIT |
| **ChatterBox Official 23-Lang v2** ★ | `t3_mtl23ls_v2.safetensors` | ~500MB | ✅ 公式 | MIT |
| **CosyVoice3 0.5B-RL** | `Fun-CosyVoice3-0.5B-RL` | ~1GB | ✅ | Apache 系 |

すべて zero-shot、事前学習不要。voice_horror 要件「事前学習なしで動く VC」に全て合致。

## 排除した候補と理由

| 候補 | 排除理由 |
|------|---------|
| **Qwen3-TTS** | TTS で重い (5-10GB ONNX)、VC 用途には言語モデルが不要 |
| **F5-TTS** | TTS-Audio-Suite で VC 非対応 (engine 内に明記) |
| **RVC** | 事前学習必須 (per-voice .pth ファイル) |
| **BERT-VITS2 / AivisSpeech** | **AGPL v3** — Steam 商用配信不可 |
| **Kokoro / MeloTTS** | Voice cloning 自体が非対応 (固定 voicepack) |
| **MOSS-TTS-Nano** | TTS+cloning モデル、ComfyUI 未統合 (Python 直接検証フェーズへ) |
| **OpenVoice v2 / GPT-SoVITS / KokoClone** | TTS-Audio-Suite に統合なし (別途検証) |

## 事前準備

### 必要ファイル

| ファイル | 配置先 | 取得方法 |
|---------|-------|---------|
| `my_sampleVoice.wav` | `ComfyUI/input/` | 既存 (自分の声、北風と太陽) |
| `girl_jp.wav` ★要作成 | `ComfyUI/input/` | VOICEVOX で少女声 20-30秒 (前 README 参照) |

`girl_jp.wav` 作成手順は `VC_TEST_README.md` の「`girl_jp.wav` の作り方」セクション参照。

### 必要モデル（既に DL 済）

```
ComfyUI/models/TTS/
├── chatterbox/English/                          ← Engine 1
├── chatterbox_official_23lang/Official 23-Lang/ ← Engine 2
└── CosyVoice/Fun-CosyVoice3-0.5B/               ← Engine 3
```

CosyVoice は初回実行時に `Fun-CosyVoice3-0.5B-RL` (RL 強化版) を自動 DL する場合あり。

## 使い方

1. ComfyUI 起動
2. `Load` → `vc_engine_compare.json`
3. `Queue Prompt`
4. 3 つの PreviewAudio で結果を聴き比べ
5. `ComfyUI/output/vh_vc_engine_*.wav` にも保存

## 検証構成

**全エンジン共通の入力**:
- source: `girl_jp.wav` (少女セリフ、内容を保持)
- narrator_target: `my_sampleVoice.wav` (自分の声、声色を取得)

→ **voice_horror 本命構図**: 少女のセリフがプレイヤー声色で再生される

| 行 | エンジン | 出力ファイル | 期待 |
|----|---------|-------------|------|
| 1 | ChatterBox 通常版 (English-only) | `vh_vc_engine_chatterbox.wav` | 日本語処理に弱い可能性 |
| 2 ★ | ChatterBox Official 23-Lang v2 | `vh_vc_engine_chatterbox23lang.wav` | 日本語ネイティブ、品質期待 |
| 3 | CosyVoice3 0.5B-RL | `vh_vc_engine_cosyvoice.wav` | 中華系、独自手法、未知数 |

## 評価チェックリスト

各エンジンの出力に対して:

| 項目 | エンジン 1 | エンジン 2 ★ | エンジン 3 |
|------|-----------|------------|-----------|
| 声色がプレイヤーに似ているか | | | |
| 内容（少女セリフ）保持 | | | |
| ノイズ・歪み | | | |
| 推論時間 | | | |
| VRAM 使用量 | | | |
| 総合 | ◎/○/△/× | ◎/○/△/× | ◎/○/△/× |

## 次のステップ判定

| 結果 | 次のアクション |
|------|--------------|
| 23-Lang が圧勝 | → Unity 統合検討 (ChatterBox 23-Lang を ONNX export スパイク) |
| CosyVoice が良い | → CosyVoice の ONNX 化可能性を調査 (ライセンス精査) |
| どれも△ | → ComfyUI 外で OpenVoice v2 / GPT-SoVITS v4 / MOSS-TTS-Nano 直接 Python で比較 |
| すべて× | → VC 路線見直し (DSP のみで実装する案へ後退) |

## トラブルシューティング: 「0:01 の無音」が返る

### 仕組み

UnifiedVoiceChangerNode は内部で発生したあらゆる例外を catch して **1秒の無音 (24kHz)** を返す設計（`voice_changer_node.py:1103-1113`）:

```python
except Exception as e:
    print(f"❌ Voice conversion failed: {e}")
    traceback.print_exc()
    empty_audio = AudioProcessingUtils.create_silence(1.0, 24000)
    return (empty_comfy, error_msg)
```

→ **0:01 = "何かしらの例外が発生" のシグナル**。実エラーは ComfyUI を起動した**ターミナル**に出力されている。

### 確認手順

1. ComfyUI 起動ターミナルウィンドウを開く
2. 直前の Queue 実行ログを探す
3. 以下の形式の traceback を見つける:

```
🔄 Voice Changer: Using <ENGINE> for voice conversion
❌ Voice conversion failed: <ここに本当の原因>
Traceback (most recent call last):
  File "...", line N, in ...
  ...
```

### 既知のエラー → 対処マッピング

| エラーパターン | 原因 | 対処 |
|--------------|------|------|
| `Voice conversion not supported. ... Please use a model with s3gen component` | ChatterBox 23-Lang VC で Japanese 等を選択 | Engine の language を **English** に切替 (s3gen は English 訓練) |
| `do not support extract speech token for audio longer than 30s` | CosyVoice の入力が 30 秒超 | source/target を 25 秒以下にトリミング |
| `CUDA out of memory` | 3 エンジン同時ロードで VRAM 不足 (RTX 2070 Super 8GB) | 行 1, 2 を mute (mode=4) して CosyVoice 単独実行 |
| `Fun-CosyVoice3-...not found` / `model_dir...` | モデル DL 失敗 | `ComfyUI/models/TTS/CosyVoice/` 確認、不足ファイルあれば再 DL |
| `flash_attn` / `vllm` / `xformers` import error | 依存パッケージ欠落 | Engine の `use_fp16=False`, `load_trt=False`, `load_vllm=False` |
| `BFloat16` 関連エラー | 一部 GPU で fp16 不一致 | use_fp16 を False、または device を `cpu` |
| `RuntimeError: shape mismatch` | sample rate / channel 不一致 | 入力 WAV を 16kHz / mono / 16-bit に正規化 |

### CosyVoice 単独で再実行する手順

3 エンジン同時ロードで VRAM 競合している可能性が高い。CosyVoice 単独で:

1. ComfyUI で 行 1（ChatterBox 通常）の VC ノードを右クリック → `Mode → Bypass` (mode=4)
2. 行 2（ChatterBox 23-Lang）の VC ノードも同様に Bypass
3. CosyVoice の VC ノードのみアクティブにして Queue Prompt
4. それでも失敗するなら CosyVoice 自体に問題

### CosyVoice をスキップして本命比較に絞る

CosyVoice が永続的に失敗する場合、**ChatterBox 通常版 vs 23-Lang v2 の 2 エンジン比較**でも判定材料は十分。それぞれ:

- ChatterBox 通常版 (English): voice encoder が英語訓練 → 日本語声色の抽出精度に上限
- ChatterBox 23-Lang v2 (English-mode VC): voice encoder が **多言語訓練** → 日本語声色の抽出精度向上を期待

VC は acoustic ベースなので両方 language=English でも source/target が日本語素材で動作する。

## 関連ファイル

- `vc_engine_compare.json` — 本 workflow（3 エンジン並列比較）
- `vc_test_chatterbox.json` — refinement_passes バリエーション workflow（前 PoC）
- `VC_TEST_README.md` — 前 PoC の README（`girl_jp.wav` 作成手順あり）

## 参照

- [ChatterBox (Resemble AI)](https://github.com/resemble-ai/chatterbox) — MIT
- [ChatterBox Official 23-Lang HF](https://huggingface.co/ResembleAI/chatterbox)
- [CosyVoice3](https://github.com/FunAudioLLM/CosyVoice) — Apache 系
- [TTS-Audio-Suite](https://github.com/diodiogod/TTS-Audio-Suite) — ComfyUI 統合
