# CosyVoice Phase 4 — ゲーム統合計画

**日付**: 2026-05-07  
**フェーズ**: Phase 4 — マイク入力・UHFPS 統合・エンディング分岐

---

## TL;DR

Phase 3 で VC パイプライン (campplus + tokenizer + DiT ODE + hift) の C# 実装と全テスト通過を達成した。  
Phase 4 はその実装をゲームに「繋ぐ」フェーズ。

主要ゴール:
1. **マイク入力 → リアルタイム VC** — プレイヤーの肉声を録音・化変換
2. **UHFPS 統合** — PlayerController + SpeakerMorphController をゲームループに接続
3. **エンディング分岐ロジック** — cosine 類似度スコアでエンディングを分岐
4. **スピーカー射影重み取得** — `extract_spk_projection.py` 実行で実重みを Unity に配置

---

## Phase 3 で確立した基盤

| コンポーネント | 状態 |
|--------------|------|
| MelExtractor.cs (STFT + mel + CMVN) | ✅ 完成 |
| SpkEmbedProjection.cs (192→80) | ✅ 完成 (JSON 重み未取得時は truncation fallback) |
| FlowMatchingODE.cs (Euler, n_steps=10) | ✅ 完成 |
| VoiceConversionPipeline.cs (4 モデル連鎖) | ✅ 完成 |
| SpeakerMorphController.cs (embedding 補間 + decay) | ✅ 完成 |
| T1–T5 全テスト通過 | ✅ 確認済み |

---

## Phase 4 タスク一覧

### 🔴 P4-T1: スピーカー射影重み取得 (前提タスク)

**目的**: SpkEmbedProjection が truncation fallback ではなく実際の学習済み線形変換を使う。

```bash
# CosyVoice3 環境で実行
cd voiceCoppy_test
python extract_spk_projection.py
# → spk_projection.json を生成 (weight [192,80], bias [80])
```

**Unity 配置**:
```
voice_Horror_Game/Assets/SentisSpike/Resources/spk_projection.json
```

SpkEmbedProjection.cs の `Load()` は既に `Resources.Load<TextAsset>("spk_projection")` に対応済み。

---

### 🔴 P4-T2: マイク入力パイプライン (MicrophoneCapture.cs)

**設計**:

```
Microphone.Start() (16kHz, 2秒バッファ)
    │
    ▼ (VAD: RMS threshold > 0.01f で発話判定)
    │ 発話区間 PCM [samples]
    ▼
VoiceConversionPipeline.ExtractSpeakerEmbedding()
    │ float[192] spk_emb
    ▼
SpeakerMorphController.RecordPlayerVoice()
    │ morphRatio 更新 + embedding 記録
    ▼
VoiceConversionPipeline.ConvertVoiceAsync()   ← coroutine (non-blocking)
    │ AudioClip (変換済み音声)
    ▼
AudioSource.PlayOneShot()  (ゲーム内に敵の声として再生)
```

**新規ファイル**: `Assets/SentisSpike/Scripts/MicrophoneCapture.cs`

```csharp
// 主要メソッド
void StartCapture()           // Microphone.Start(), バッファ初期化
void StopCapture()            // Microphone.End()
void Update()                 // VAD → 発話区間 detect → coroutine 起動
IEnumerator ProcessVoice()    // ExtractSpeakerEmbedding → RecordPlayerVoice → ConvertVoiceAsync
```

**VAD 実装** (シンプル RMS 閾値):
```csharp
float rms = 0;
for (int i = 0; i < samples.Length; i++) rms += samples[i] * samples[i];
rms = Mathf.Sqrt(rms / samples.Length);
bool isSpeaking = rms > k_VadThreshold; // 0.01f
```

**留意点**:
- Unity `Microphone.Start()` は Play Mode でのみ動作 (Edit Mode 不可)
- 録音 SR = 16000 Hz (campplus 入力要件)
- ConvertVoiceAsync は GPU を使うため coroutine で 1 フレーム yield を挟む
- 変換出力 AudioClip を再生するかどうかはゲームデザイン判断 (試聴 / 敵声置換 等)

---

### 🟡 P4-T3: SpeakerMorphController → UHFPS PlayerController 統合

**接続先**: `ThunderWire Studio/UHFPS/` の `PlayerController.cs` (または同等の入力ハンドラ)

**手順**:
1. UHFPS PlayerController の Update / FixedUpdate で `MicrophoneCapture.IsSpeaking` を参照
2. 声を出した際に SpeakerMorphController.RecordPlayerVoice を呼ぶのは MicrophoneCapture が担当 → 直接統合は不要
3. ゲーム内「声を出したら敵が強化」メカニクスのために `morphRatio` を EnemyAIManager に公開

```csharp
// EnemyAIManager.cs に追加予定
[SerializeField] SpeakerMorphController _morphCtrl;

float EnemyStrengthMultiplier => 1f + _morphCtrl.morphRatio * k_MaxStrengthBonus;
```

**UHFPS 依存の注意点**:
- UHFPS の AI / Inspector 設定は `ThunderWire Studio/` 配下で直接変更しない
- ラッパークラス (`VoiceHorrorGameManager.cs` 等) を新規作成して注入する

---

### 🟡 P4-T4: VC 変換を完全非同期化 (ConvertVoiceAsync 呼び出し側)

Phase 3 の `ConvertVoiceAsync` は coroutine 実装済み。Phase 4 では呼び出し側の整備が必要。

**問題**: GPU forward (DiT ODE × 10 steps) は 1 フレームに収まらない場合がある。

**対策**:
```csharp
// MicrophoneCapture.cs 内
IEnumerator ProcessVoice(AudioClip captured)
{
    _isProcessing = true;
    yield return StartCoroutine(
        _vcPipeline.ConvertVoiceAsync(captured, _morphCtrl.GetMorphedEmbedding(),
            clip => {
                _morphCtrl.RecordPlayerVoice(_lastExtractedEmb);
                if (clip != null && _playConvertedAudio)
                    _audioSrc.PlayOneShot(clip);
            }));
    _isProcessing = false;
}
```

**パフォーマンス目標**:
- campplus forward: < 100ms (28 MB モデル)
- DiT ODE 10 steps: < 2000ms (1268 MB モデル、GPUCompute)
- hift forward: < 500ms (329 MB モデル)
- **合計目標: < 3 秒 (プレイヤーが話し終わってから 3 秒で変換完了)**

---

### 🟡 P4-T5: エンディング分岐ロジック (EndingManager.cs)

**ゲームデザイン仕様**:

| 条件 | エンディング |
|------|------------|
| cosine 類似度 > 0.85 | BAD END — 少女幽霊にカラダを奪われる |
| cosine 類似度 < 0.85 | GOOD END — 脱出成功 |
| morphRatio > 0.5 かつ類似度 < 0.85 | BAD END — 声色を変えて攻略、少女が電話を切る |

**新規ファイル**: `Assets/Scripts/Game/EndingManager.cs`

```csharp
public class EndingManager : MonoBehaviour
{
    [SerializeField] SpeakerMorphController _morphCtrl;

    const float k_SimilarityThreshold = 0.85f;
    const float k_MorphThreshold      = 0.5f;

    public EndingType DetermineEnding()
    {
        float sim   = _morphCtrl.ComputeSimilarity();
        float morph = _morphCtrl.morphRatio;

        if (sim >= k_SimilarityThreshold)
            return EndingType.BadEnd_Possessed;  // カラダを奪われる

        if (morph >= k_MorphThreshold && sim < k_SimilarityThreshold)
            return EndingType.BadEnd_PhoneHangup; // 声色変更、電話を切られる

        return EndingType.GoodEnd;
    }
}

public enum EndingType { GoodEnd, BadEnd_Possessed, BadEnd_PhoneHangup }
```

---

### 🟢 P4-T6: DiT n_steps パフォーマンス調整

Phase 3 は n_steps=10 固定。3〜5 steps でも品質が許容範囲か検証する。

| n_steps | DiT ODE 時間 (推定) | 品質 |
|---------|-------------------|------|
| 3 | ~600ms | 要確認 |
| 5 | ~1000ms | 要確認 |
| 10 | ~2000ms | Phase 3 確認済 |

**テスト方法**: `VoiceConversionPipeline.odeSteps` を Inspector で変更し、実音声で聴感評価。

---

### 🟢 P4-T7: 少女幽霊 reference audio 録音 → girlGhostEmb 計算

**手順**:
1. 少女幽霊の声 (TTS で生成 or 録音) を `girl_ghost_ref.wav` として用意
2. `VoiceConversionPipeline.ExtractSpeakerEmbedding(girlGhostRefClip)` を Editor スクリプト経由で実行
3. 出力 float[192] を `Assets/SentisSpike/Resources/girl_ghost_emb.json` に保存
4. `SpeakerMorphController.girlGhostEmb` に Inspector から設定

**Editor スクリプト追加予定**: `SentisSpikeSetupPhase4.cs` に "Compute girlGhostEmb" メニュー項目

---

## Phase 4 テスト計画 (T1–T6)

| テスト | 内容 | 判定基準 |
|--------|------|---------|
| T1 | MicrophoneCapture 初期化 + VAD 動作 | マイク起動、RMS 閾値で isActive 変化 |
| T2 | 実音声 → ExtractSpeakerEmbedding → emb[192] | shape 正常、NaN なし |
| T3 | spk_projection.json ロード → 実重みで projection | fallback と異なる値が出る |
| T4 | E2E: マイク → VC → AudioClip 再生 | 例外なし、AudioClip.length > 0 |
| T5 | SpeakerMorphController decay 動作確認 | 30 秒後に morphRatio が初期増分の 50% に収束 |
| T6 | EndingManager.DetermineEnding() 分岐 | 3 ケース全て正常に分岐 |

---

## 実装順序 (推奨)

```
P4-T1 (spk_projection.json 取得)
    ↓
P4-T2 (MicrophoneCapture.cs 実装 + T1/T2 テスト)
    ↓
P4-T5 (EndingManager.cs 実装 + T6 テスト)
    ↓
P4-T3 (UHFPS 統合 + T4/T5 テスト)
    ↓
P4-T6 (n_steps 調整 — 聴感評価)
    ↓
P4-T7 (girlGhostEmb 計算 + 配置)
```

---

## 関連ファイル

- Phase 3 レポート: `docs/reports/spikes/2026-05-07_cosyvoice-phase3-pipeline.md`
- VC パイプライン: `voice_Horror_Game/Assets/SentisSpike/Scripts/VoiceConversion/`
- spk projection 抽出: `voiceCoppy_test/extract_spk_projection.py`
- ONNX fix スクリプト: `voiceCoppy_test/fix_flow_onnx.py`, `fix_hift_onnx.py`
- Sentis トラブルシューティング: `docs/reports/sentis-onnx-import-troubleshooting.md`
