# Unity Sentis 2.5 ONNX インポート トラブルシューティングガイド

作成: 2026-05-07  
対象: Unity Inference Engine (Sentis) 2.5 (`com.unity.ai.inference 2.5.0`)  
名前空間: `Unity.InferenceEngine`  
検証モデル: CosyVoice3 0.5B-RL の 4 モデル (campplus / speech_tokenizer / flow.decoder.estimator / hift)

---

## 背景

PyTorch で訓練・ONNX export したモデルをそのまま Sentis に渡すと、ほぼ確実に複数のエラーが発生する。
本ドキュメントはその全パターンと修正方法を記録したものである。
修正は Python (onnx ライブラリ) でグラフを書き換えてから Unity に渡す方式を採用した。

---

## 前提環境

```
Unity     6000.3.9f1
Sentis    com.unity.ai.inference 2.5.0
Python    3.10+
onnx      1.16+  (pip install onnx)
numpy     1.26+
```

---

## 問題一覧

| # | エラー / 症状 | 影響モデル | カテゴリ |
|---|---|---|---|
| 1 | `ValueError: broadcast dims must be equal or 1` | hift, flow.decoder | rank-0 initializer |
| 2 | `Object reference not set to an instance of an object` | flow.decoder | LayerNorm bias 欠落 |
| 3 | `IndexOutOfRangeException` at `DFT.Execute` line 108 | hift | DFT axis 入力欠落 |
| 4 | `Compute shader (Clip): Property (Bptr) at kernel index (0) is not set` | hift | Clip min/max 欠落 |
| 5 | rank ミスマッチ (downstream で shape 衝突) | hift, flow.decoder | Gather scalar-index |
| 6 | `expecting X, got Y` (rank 衝突) | hift, flow.decoder | value_info 干渉 |
| 7 | DFT 出力 shape 誤推定 → broadcast エラー | hift | Sentis DFT.InferPartial バグ |

---

## 修正 1: rank-0 initializer を rank-1 に変換

### 症状
```
ValueError: broadcast dims must be equal or 1
```
ONNX の scalar 定数（shape = `[]`、rank = 0）を Sentis は許容しない。

### 原因
PyTorch の `torch.onnx.export` は scalar テンソル（例: `torch.tensor(0)`, `torch.tensor(1.0)`）を
rank-0 の initializer として export する。Sentis は rank ≥ 1 を期待する。

### 修正コード
```python
rank0_init_names = set()
for init in model.graph.initializer:
    if len(init.dims) == 0:
        rank0_init_names.add(init.name)
        del init.dims[:]
        init.dims.extend([1])  # [] → [1]
```

### 注意
rank-0 → rank-1 にした initializer が **Gather の index として使われている場合**、
問題 5（Gather scalar-index）が連鎖して発生する。下記修正 5 を必ずセットで適用すること。

---

## 修正 2: LayerNormalization の bias (input[2]) を追加

### 症状
```
NullReferenceException: Object reference not set to an instance of an object
  at Unity.InferenceEngine.Layers.LayerNormalization.Execute(...)
```

### 原因
Sentis の ONNX インポーター (`ONNXModelConverter.cs`) のコード:
```csharp
case "LayerNormalization":
{
    var epsilon = node.GetOptionalFloat("epsilon", 1e-5f);
    SetOutput(gm.LayerNormalization(GetInput(0), GetInput(1), GetInput(2), epsilon));
    break;
}
```
`GetInput(2)` が bias を返す。PyTorch の `nn.LayerNorm(bias=False)` で export したモデルは
input[2] が存在せず → null → `gm.LayerNormalization` 内部で NullReferenceException。

### 修正コード
```python
# scale (input[1]) の shape を取得して zero bias を作成
LN_BIAS_NAME = "__ln_zero_bias__"
scale_shape = None
for init in model.graph.initializer:
    if init.name == "val_55":  # 実際の scale tensor 名に合わせる
        scale_shape = list(init.dims)
        break

if scale_shape is None:
    scale_shape = [512]  # fallback: モデルの hidden_dim

zero_bias = numpy_helper.from_array(
    np.zeros(scale_shape, dtype=np.float32), name=LN_BIAS_NAME)
model.graph.initializer.append(zero_bias)

for node in model.graph.node:
    if node.op_type == "LayerNormalization":
        if len(node.input) < 3:
            node.input.append(LN_BIAS_NAME)
        elif not node.input[2]:
            node.input[2] = LN_BIAS_NAME
```

### 注意
- zero bias は数学的に「bias なし」と等価（`y = scale * (x - mean) / std + 0`）なので精度への影響はない
- scale tensor の名前は `model.graph.initializer` を走査して実際の名前を確認すること

---

## 修正 3: DFT の axis 属性を input[2] に昇格

### 症状
```
IndexOutOfRangeException: Index was outside the bounds of the array.
  at Unity.InferenceEngine.Layers.DFT.Execute(...)
  Layer.Spectral.cs:108
```

### 原因
ONNX opset 17 の DFT は `axis` を **attribute** として持つ（inputs は `input`, `dft_length` のみ）。
Sentis インポーターは `GetInput(2)` で axis を取得しようとするが、
opset 17 モデルには input[2] が存在しないため `inputs[2] = -1` になる。
実行時に:
```csharp
int axis = ctx.storage.GetInts(inputs[2])[0];  // inputs[2]=-1 → 空配列 → IndexOutOfRange
```

### 修正コード
```python
DFT_AXIS_CONST = "__dft_axis__"

# axis 属性値を読む
dft_axis_val = 2  # default
for node in model.graph.node:
    if node.op_type == "DFT":
        for a in node.attribute:
            if a.name == "axis":
                dft_axis_val = int(a.i)

# Constant ノードを追加
axis_tensor = helper.make_tensor(DFT_AXIS_CONST, TensorProto.INT64, [1], [dft_axis_val])
axis_node = helper.make_node("Constant", [], [DFT_AXIS_CONST],
                             name="const_dft_axis", value=axis_tensor)
model.graph.node.insert(0, axis_node)  # グラフ先頭 or DFT の前ならどこでも可

# DFT ノードの input[2] に設定
for node in model.graph.node:
    if node.op_type == "DFT":
        while len(node.input) < 2:
            node.input.append("")  # dftLength 省略
        while len(node.input) < 3:
            node.input.append(DFT_AXIS_CONST)
        if not node.input[2]:
            node.input[2] = DFT_AXIS_CONST
```

---

## 修正 4: Clip ノードの min/max 欠落を ±inf で補完

### 症状
```
Compute shader (Clip): Property (Bptr) at kernel index (0) is not set
```
テストは通るが毎フレーム警告が出る。

### 原因
ONNX opset 11+ の Clip は min/max を optional input として持つ。
「min のみ指定・max なし」の Clip ノードでは Sentis が GPU compute shader の
`Bptr`（max バッファ）を bind しないが、Unity の driver は全 property の bind を要求する。

- `Bptr` = max バッファ（`UseMax` keyword で有効化）
- `Sptr` = min バッファ（`UseMin` keyword で有効化）

### 修正コード
```python
import numpy as np

CLIP_INF    = "__clip_max_inf__"
CLIP_NEGINF = "__clip_min_neginf__"

model.graph.initializer.append(
    numpy_helper.from_array(np.array(float("inf"),  dtype=np.float32), name=CLIP_INF))
model.graph.initializer.append(
    numpy_helper.from_array(np.array(float("-inf"), dtype=np.float32), name=CLIP_NEGINF))

for node in model.graph.node:
    if node.op_type != "Clip":
        continue
    while len(node.input) < 3:
        node.input.append("")
    if node.input[1] == "":    # min 欠落
        node.input[1] = CLIP_NEGINF
    if node.input[2] == "":    # max 欠落
        node.input[2] = CLIP_INF
```

### 注意
±inf クリップは数学的に no-op なので出力への影響はゼロ。

---

## 修正 5: Gather の scalar-index 問題

### 症状
修正 1 適用後に下流で rank が +1 ずれて shape 衝突が多発する。

### 原因
ONNX Gather の動作:
- rank-0 (scalar) index → axis 次元を **除去** → output rank = data_rank - 1
- rank-1 (size=1) index → axis 次元を **1 で残す** → output rank = data_rank  ← 修正 1 後

rank-0 initializer を rank-1 に変えると、それを index に使う Gather の出力 rank が +1 になり、
下流の全ノードで rank ミスマッチが発生する。

### 修正コード
```python
# rank-0 initializer を index とする Gather の直後に Squeeze を挿入
for node in model.graph.node:
    if (node.op_type == "Gather"
            and len(node.input) > 1
            and node.input[1] in rank0_init_names):  # rank0_init_names: 修正1で収集
        
        axis = 0
        for a in node.attribute:
            if a.name == "axis":
                axis = int(a.i)
        
        # Gather 出力を tmp 名に変更し、Squeeze で rank を元に戻す
        orig_out = node.output[0]
        tmp_out  = orig_out + "__sq_tmp__"
        node.output[0] = tmp_out
        
        axes_tensor = helper.make_tensor("__sq_axes__", TensorProto.INT64, [1], [axis])
        axes_node   = helper.make_node("Constant", [], ["__sq_axes__"], value=axes_tensor)
        squeeze     = helper.make_node("Squeeze", [tmp_out, "__sq_axes__"], [orig_out])
        # axes_node と squeeze を DFT の直前 or グラフ末尾に追加
```

実際の実装では axes constant を axis 値ごとに 1 つ作り、全対象 Gather に共有する。

---

## 修正 6: value_info を全削除

### 症状
```
DynamicTensorShapeMismatchException: expecting rank X, got Y
```
または shape 関連の assert 失敗。

### 原因
`onnx.shape_inference.infer_shapes()` が付与した `value_info`（中間テンソルの shape 宣言）が
Sentis の `InferPartial` による動的 rank 推論と衝突する。

### 修正コード
```python
del model.graph.value_info[:]
```

これだけ。Sentis が全テンソルを DynamicRank スタートで推論しなおす。
副作用はなく、推論速度にも影響しない。

---

## 修正 7: Sentis DFT.InferPartial バグの回避（逆 DFT + onesided）

### 症状
```
ValueError: broadcast dims must be equal or 1
```
DFT を含むモデルで broadcast エラーが下流ノードに発生する。

### 原因
Sentis の `DFT.InferPartial` (Layer.Spectral.cs) は onesided DFT の出力長を常に
`N/2 + 1` と推定する（実装: `outputXformSignalLength = onesided ? dftLength/2+1 : dftLength`）。  
**逆 DFT (inverse=1, onesided=1)** の正しい出力長は `dftLength`（元の時間長）だが、
Sentis はこれを `N/2 + 1` と誤推定するため、下流で shape の不一致が発生する。

### 修正方針: Hermitian 拡張 + onesided=0 に変更

逆 DFT への入力は Hermitian 対称なスペクトル（片側 N/2+1 ビン）。
これを全スペクトル（N ビン）に拡張してから onesided=0 で逆変換すると、
InferPartial が `output_length = dftLength = N` と正しく推定する。

**Hermitian 拡張**: 片側スペクトル `[DC, b1, b2, ..., b7, Nyquist]`（9 bins, N=16）を
`[DC, b1, ..., b7, Nyquist, conj(b7), ..., conj(b1)]`（16 bins）に拡張する。
共役 = 実部そのまま、虚部の符号反転（`* [1.0, -1.0]`）+ 逆順（`b7..b1`）。

```python
# Sentis でのモデル保存前に以下を適用
# 1. 片側ビン bins[1..7] を抽出して共役・逆順にする
# 2. 元スペクトルと concat して全スペクトルを構成
# 3. DFT の onesided 属性を 0 に変更
# (詳細実装は fix_hift_onnx.py の Step 6 を参照)
```

### 影響
- 数学的に等価（Hermitian input の IDFT は実数）
- ヴォコーダ音質への影響なし

---

## 修正 8: ReduceSum の axes は変換しない（重要な誤りパターン）

### ⚠️ やってはいけない修正

ONNX opset 18 で ReduceSum の `axes` が attribute から input[1] に移動した際、
「Sentis が attribute しか読まない」と誤解して以下の変換をしたくなるが、**これは誤り**:

```python
# ❌ 誤り: axes を attribute に移動すると input[1] が消え、Sentis が null を受け取る
new_node = helper.make_node(
    "ReduceSum",
    inputs=[node.input[0]],   # axes input を削除
    outputs=list(node.output),
    name=node.name,
    axes=axes_vals,           # attribute として設定
)
```

### 正しい理解
Sentis の `ONNXModelConverter.cs` の ReduceSum 処理（line 1116-1136）:
```csharp
// opset >= 13 では input[1] から axes を読む (attribute は無視)
if (node.InputCount > 1 && node.Input(1) != "")
    axes = node.GetInts(1);
```

opset 18 の input[1] ベースの axes をそのまま残すことが正解。変換は不要。

---

## 全体的なワークフロー

```
PyTorch モデル
    ↓ torch.onnx.export
raw .onnx
    ↓ Python 修正スクリプト (fix_*.py)
      1. rank-0 initializer → rank-1
      2. Gather scalar-index fix (Squeeze 挿入)
      3. Range 入力に Squeeze 挿入 (opset 18+)
      4. value_info 全削除
      5. graph.input/output rank-0 修正
      6. DFT axis 属性 → input[2] 昇格
      7. DFT InferPartial バグ回避 (Hermitian 拡張 + onesided=0)
      8. LayerNorm zero bias 追加 (bias=False モデル)
      9. Clip min/max 補完 (±inf)
fixed .onnx
    ↓ Unity Assets/ にコピー
Sentis ModelAsset
```

---

## 診断スクリプト一覧

| スクリプト | 用途 |
|---|---|
| `voiceCoppy_test/diag_flow_decoder.py` | flow.decoder の op census / rank-0 / broadcast シミュレーション |
| `voiceCoppy_test/diag_hift_dft_trace.py` | hift の DFT 入出力チェーンを遡ってトレース |
| `voiceCoppy_test/diag_hift_expand_v2.py` | Expand / ConstantOfShape / Greater ノードを追跡 |

---

## 修正スクリプト一覧

| スクリプト | 対象モデル | 主な修正 |
|---|---|---|
| `voiceCoppy_test/fix_hift_onnx.py` | hift.fp32.onnx | rank-0 / Gather / Range / value_info / DFT Hermitian + axis / Clip |
| `voiceCoppy_test/fix_flow_onnx.py` | flow.decoder.estimator.fp32.onnx | rank-0 / Gather / LayerNorm bias / value_info |

---

## Tips

### 外部データ (.data ファイル) を持つ大型モデル
1 GB 超のモデルは `onnx.save(..., save_as_external_data=True)` で分割される。
グラフ修正時は重みを読み込まずグラフ構造だけ処理する:

```python
model = onnx.load("model.onnx", load_external_data=False)
# ... グラフ修正 ...
onnx.save(model, "model_fixed.onnx")  # .data は変更されず参照を保持
```

`.onnx` と同じディレクトリに `.data` ファイルがある必要がある。

### ONNX checker で事前検証
```python
onnx.checker.check_model(model)  # トポロジカル順序・型整合性を確認
```
ただし Sentis 固有のバグ（InferPartial の誤推定など）は ONNX checker では検出できない。

### Sentis が InferPartial エラーを出す場合の第一手
```python
del model.graph.value_info[:]  # これだけで解決するケースが多い
```

### GPU backend vs CPU backend
`BackendType.GPUCompute` が最速だが、一部の op は CPU のみ対応。
クラッシュが続く場合は `BackendType.CPU` で動作確認してから GPU を試す。
