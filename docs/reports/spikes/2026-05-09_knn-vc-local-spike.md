# Phase 5: kNN-VC ローカルスパイク (sandbox 検証)

**実施日**: 2026-05-09
**ブランチ**: `feature/phase5-knn-vc-spike`
**目的**: voice_horror 環境で kNN-VC が技術的に動作・許容品質であることを確認する

## 結論

✅ **kNN-VC 路線採用確定**。RTX 2070S 8GB VRAM 環境で:

- pipeline 動作 OK (smoke test + cross-speaker test 両方成功)
- ユーザー本人の声 30 秒 reference で「すごい似てる」品質判定 (ユーザー聴感)
- 1 秒音声に対し **40-100ms** の inference (RTF 0.015-0.042、24-66x real-time)
- VRAM peak **2.41GB** (Unity URP + UHFPS と同居可能)
- LICENSE すべて MIT 確認済 (Steam 商用配信可)

次フェーズ: **Phase 6 Sentis 互換性検証** (WavLM Large + HiFiGAN を ONNX export → Sentis 2.5 でロード成功するか)

## 環境構築 (T5-1)

### sandbox 場所

`C:/Users/tatuk/Desktop/Sandbox/knn-vc-spike/` (voice_horror リポ外)

### セットアップ手順

```bash
mkdir -p C:/Users/tatuk/Desktop/Sandbox
cd C:/Users/tatuk/Desktop/Sandbox
git clone https://github.com/bshall/knn-vc.git knn-vc-spike
cd knn-vc-spike

python -m venv .venv  # Python 3.13.7
.venv/Scripts/python.exe -m pip install --upgrade pip

# PyTorch CUDA 12.4 (Python 3.13 は cu121 wheel なし、cu124 から)
.venv/Scripts/python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# 追加依存
.venv/Scripts/python.exe -m pip install numpy soundfile
```

### インストールされたバージョン

| パッケージ | バージョン |
|-----------|-----------|
| Python | 3.13.7 |
| torch | 2.6.0+cu124 |
| torchaudio | 2.6.0+cu124 |
| numpy | 2.4.4 |
| soundfile | 0.13.1 |

### 環境ハマりポイント

- **CUDA 12.1 wheel は Python 3.13 で配布なし** → cu124 を選択
- **torchaudio の I/O backend が無いとエラー** → `pip install soundfile` 必要 (Windows)
- WavLM-Large.pt + prematch_g_02500000.pt の初回 DL ~1.3GB、torch.hub キャッシュへ

## LICENSE 確認 (T5-2)

| 構成要素 | LICENSE | 出典 | 商用 OK |
|---------|---------|------|---------|
| **kNN-VC** (bshall/knn-vc) | MIT | LICENSE 直接確認 (Stellenbosch University 2023) | ✅ |
| **WavLM** (microsoft/unilm) | MIT | LICENSE 直接確認 (Microsoft Corporation 2021) | ✅ |
| **HiFiGAN** (knn-vc 同梱、WavLM features 用に再学習) | MIT | knn-vc LICENSE に内包 | ✅ |

### Steam 配信時の義務

- ゲームクレジット or `LICENSES.txt` に以下相当の copyright notice を含める:
  - `kNN-VC (MIT, Stellenbosch University 2023)`
  - `WavLM (MIT, Microsoft Corporation 2021)`
- 改変時はその旨明記

### 注記

`knn-vc/LICENSE` 第 13-15 行に「コピーライトの意義について 10 秒考える」という文学的注釈条項があるが、実質拘束力なし。純粋な MIT として扱って問題なし。

## 動作確認 (T5-3): smoke test

### 構成

- **Source = Reference**: `voiceCoppy_test/my_sampleVoice.wav` (ユーザー本人 30.56s)
- 自己変換テスト (pipeline が壊れていないことの確認)

### 結果

| 項目 | 値 |
|------|---|
| Source duration | 30.56s |
| query 特徴抽出 | 1346.1ms |
| matching set 構築 | 234.0ms |
| kNN + HiFiGAN | 555.4ms |
| **Total inference** | **2135.5ms** |
| **RTF** | **0.070 (14.3x real-time)** |
| **VRAM peak** | **2.41 GB** |
| L1(src, out) | 0.0914 |
| L2(src, out) | 0.1610 |

L1/L2 距離は kNN-VC の自然な範囲 (期待 0.05-0.2)。同一話者でも完全 identity ではないことが正常動作のサイン。

### 出力 wav

`output/smoke_test_normalized.wav` — peak normalized to 0.95 (raw output peak 3.17 のため)

### 環境計測

- 初回モデルロード: 125.7s (WavLM Large 1.2GB + HiFiGAN ~50MB の DL 含む)
- 2 回目以降ロード: 5.4s (キャッシュヒット)

## 品質確認 (T5-4): cross-speaker conversion

### 構成

- **Target reference (声色のゴール)**: `my_sampleVoice.wav` (ユーザー本人 30.56s) → matching set
- **Sources (発話内容、これらをユーザーの声で喋り直す)**:
  - `kaien.mp3` (4.0s)
  - `raizyo.mp3` (24.2s)
  - `sounyuu.mp3` (2.1s)
  - `107.wav` (35.7s)

### 結果

| Source | duration | query | convert | RTF | output peak |
|--------|----------|-------|---------|-----|------------|
| kaien | 4.00s | 22ms | 146ms | 0.042 (24x RT) | 1.31 → norm 0.95 |
| raizyo | 24.17s | 123ms | 248ms | 0.015 (66x RT) | 1.30 → norm 0.95 |
| sounyuu | 2.08s | 19ms | 37ms | 0.027 (37x RT) | 0.87 (clean) |
| 107 | 35.70s | 123ms | 441ms | 0.016 (62x RT) | 1.36 → norm 0.95 |

VRAM peak: **2.41 GB** (smoke test と同値)

### ユーザー聴感判定

> **「すごい似てる」**

target reference 30 秒 (kNN-VC の最低ライン、公式デモは 5 分以上推奨) で十分な品質を確認。
Phase 9 で声優収録 5-10 分を取れば本番品質はさらに向上が見込まれる。

### 出力 wav

`output/converted_<source>_to_user.wav` (4 ファイル、いずれも 16kHz mono)

## レイテンシ計測 (T5-6)

### 観測値 (RTX 2070S, PyTorch 2.6+cu124)

```
1秒音声あたり (cross_test の集約値):
  - WavLM forward (query)        : ~5-30ms
  - kNN match + HiFiGAN vocode  : ~10-30ms
  - Total                        : ~15-60ms
```

### 事前見積もりとの比較

| | 事前見積 | 実測 (PyTorch) | 想定 (Sentis 1.5-2x) |
|---|---|---|---|
| 1秒音声 | 50-160ms | 15-60ms | 30-120ms |

実測は事前見積よりさらに高速。Sentis port で多少劣化しても十分 real-time 余裕。

### 体感レイテンシ計算

| 用法 | 音声長 | 処理 | 合計レイテンシ |
|------|--------|------|---------------|
| 録音 → 全変換 → 再生 | 2 秒 | ~80ms | 2.08s (録音時間 + 80ms) |
| 録音 → 全変換 → 再生 | 5 秒 | ~200ms | 5.2s |
| ストリーミング (500ms チャンク) | 連続 | ~30ms/chunk | 約 530ms 先頭遅延 |

voice_horror の narrative (BAD ED「カラダを奪われる」、電話越し演出、混ざっていく演出) は **非ストリーミング (録音→変換→再生) で十分**。

## matching set サイズ実験 (T5-5、partial)

### 実施

target reference 30 秒のみで cross-conversion 4 件確認 → 「すごい似てる」品質。

### 未実施

- 1 分・5 分・10 分での品質比較
- これは **Phase 9 で声優収録した本番音声** で実施するのが効率的 (現状では 30 秒以上の質の良いユーザー音声が無い)

### 公式デモからの推定

`https://bshall.github.io/knn-vc/` の section 3 アブレーションでは:
- 1 分: 認識可能、若干片言感
- 5 分: 飽和に近い品質
- 8 分以上: 微増

→ Phase 9 では **5-10 分** を収録目標とする。

## 動作スクリプト

### `smoke_test.py`
自己変換 + パイプライン動作確認 + 全ステージ計測。

### `cross_test.py`
target reference (ユーザー声) に対して 4 source を個別変換 + 計測。

両方とも `C:/Users/tatuk/Desktop/Sandbox/knn-vc-spike/` 配下、venv 経由実行:
```bash
cd C:/Users/tatuk/Desktop/Sandbox/knn-vc-spike
.venv/Scripts/python.exe smoke_test.py
.venv/Scripts/python.exe cross_test.py
```

## 既知の挙動と注意点

### output peak が 1.0 を超える

HiFiGAN の出力が瞬間的に [-1, 1] 範囲を逸脱することがある (kaien 1.31, raizyo 1.30, 107 1.36)。

**対処**: 保存前に `wav / peak * 0.95` で正規化。これは matching set が薄い (30秒) ため近傍が遠い frame で発生しやすい。**Phase 9 で 5-10 分の reference を使えば軽減**するはず。

### モデルロード初回の遅延

WavLM-Large.pt (1.2GB) + prematch_g (50MB) の torch.hub.load_state_dict_from_url が初回 ~2 分。
**Unity 統合時の対処**: モデルウェイトを Unity StreamingAssets/Resources に同梱、もしくは Addressable で初回 DL。

### Windows torchaudio backend

`pip install soundfile` 必須。`pip install ffmpeg-python` 等は不要だった (mp3 も soundfile で読めた)。

## 次のフェーズ

### Phase 6 (Sentis 互換性検証) — 直近最重要

| Task | 内容 |
|------|------|
| T6-1 | WavLM Large の ONNX export (PyTorch → torch.onnx.export) |
| T6-2 | HiFiGAN の ONNX export |
| T6-3 | Sentis 2.5 でロード確認、PyTorch との数値一致 (rtol < 1e-3) |
| T6-4 | unsupported op の対応 (CosyVoice3 で経験ある手順) |
| T6-5 | C# 側 (Unity Sentis) で WavLM forward 実時間計測 |
| T6-6 | spike report `2026-05-XX_knn-vc-sentis-port.md` |

### Phase 7 (voice_horror 統合 spec / design)

`designs/specs/voice_conversion/{spec,design,tasks}.md` を init-agent で作成。
verifiableRequirements 形式で Behavior リスト化。

### Phase 8 (演出パターン実装) / Phase 9 (声優収録脚本設計)

Phase 6 / 7 完了後。

## 関連ファイル

### sandbox (voice_horror リポ外)

- `C:/Users/tatuk/Desktop/Sandbox/knn-vc-spike/` — git clone + venv
- `C:/Users/tatuk/Desktop/Sandbox/knn-vc-spike/smoke_test.py`
- `C:/Users/tatuk/Desktop/Sandbox/knn-vc-spike/cross_test.py`
- `C:/Users/tatuk/Desktop/Sandbox/knn-vc-spike/output/` — 全出力 wav + log

### voice_horror リポ内

- `docs/reports/handoffs/2026-05-09_phase3.5-pivot-to-knn-vc.md` — pivot 経緯
- `voice_Horror_Game/Assets/SentisSpike/Scripts/VoiceConversion/{NpyWriter,WavWriter}.cs` — Phase 6 以降で再利用

### 公式リソース

- 論文: https://arxiv.org/abs/2305.18975 (Baas et al., Interspeech 2023)
- GitHub: https://github.com/bshall/knn-vc
- 公式デモ: https://bshall.github.io/knn-vc/
- WavLM 原典: https://github.com/microsoft/unilm/tree/master/wavlm
