---
name: generate-char-designs
description: キャラクターデザイン案をFlanime v3.0 + ComfyUI on Kaggleで大量生成する。キャラ設定からプロンプトを自動生成し、ノートブックに書き込む。img2imgによる画風統一にも対応。
user-invocable: true
argument-hint: <キャラ設定 or "img2img" or "list" or "from-gdd">
---

# Generate Character Designs: $ARGUMENTS

キャラクター設定からFlanime v3.0 + Derpina LoRA用のプロンプトを生成し、ComfyUI on Kaggleノートブックに書き込む。

## 参考資料 (プロンプト生成時に必ず参照)

- **プロンプトTips**: `docs/wiki/キャラクター画像_プロンプトTips.md` — 語順ルール、ポーズ3層、ネガティブ設計、パラメータ設定
- **リサーチドキュメント**: `designs/game-image-gen-agent-research.md` — Section 7: 実証済みパイプライン
- **成功例**: `output/char_designs/fav/` — ユーザーが選定したお気に入りデザイン

## 実証済みパイプライン (全ステップ動作確認済み)

```
Phase A: デザイン探索        → Kaggle ComfyUI txt2img [無料]
Phase B: 細部調整・仕上げ    → nano banana / GPT / Gemini [無料枠]
Phase C: 画風統一            → Kaggle ComfyUI img2img [無料]
Phase D: ターンアラウンド    → GPT / Gemini / nano banana [無料枠]
Phase E: パーツ分解          → Gemini / GPT / nano banana [無料枠]
Phase F: リグ・アニメーション → AnyPortrait ($49)
```

## 実行環境

- **モデル**: RIN Flanime Illustrious v3.0 (Kaggle private dataset: `bigbigzabuton/rin-flanime-illustrious-v30`)
- **LoRA**: Derpina GF 0.9 (同dataset)
- **実行**: ComfyUI on Kaggle T4 (git clone → API経由生成)
- **HiresFix**: 1.5x upscale + denoise 0.45
- **Clip skip**: 2, **CFG**: 5.0, **Steps**: 28, **Sampler**: euler_ancestral

## 引数パターン

### 直接指定
```
/generate-char-designs シスター・マリア 10歳 金髪ロング 青目 修道服 おとなしい性格
```

### 複数キャラ（改行区切り）
```
/generate-char-designs
シスター・マリア: 10歳、金髪ロング、青目、修道服、おとなしい
骸骨騎士: アンデッド、白銀鎧、青い眼光、白マント、金装飾
蜂キメラ: 巨大蜂の体、老人の顔、複眼、牙、血管の縫合
```

### img2img (画風統一・デフォルメ化)
```
/generate-char-designs img2img 骸骨騎士をシスターさんの画風に合わせる
```

### GDDから
```
/generate-char-designs from-gdd
```

### 一覧確認
```
/generate-char-designs list
```

## プロンプト生成ルール

### 語順 (Tips準拠: 先頭ほど影響大)
```
品質タグ(1-2個) → 人数 → 外見(髪/目) → 服装 → ポーズ3層 → 構図 → 背景
```

### 品質タグ
- **デフォルト**: `best quality, newest`
- **品質重視時**: `best quality, very aesthetic, newest, absurdres`
- 乱用禁止（均一な見た目になる）

### ポーズ3層レイヤリング
```
Layer 1: ベース姿勢  — standing / sitting / running
Layer 2: 身体修飾    — hands clasped / arms behind back / holding book
Layer 3: 感情・文脈  — gentle smile / looking down / excited expression
```

### ベールのあるキャラの髪型制約
- ○ 使える: long hair, bob cut, side braid, wavy hair, hime cut, sidelocks
- × 使えない: ponytail, twintails, double bun, drill hair（ベール貫通）

### ネガティブプロンプト (固定)
```
nsfw, nude, lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, bad pupils, mismatched pupils
```
**Derpina LoRA使用時は `nsfw, nude` が必須**（白い服=ヌード誤認バグ）

### キャラ種別ネガティブ追加
- **武器持たせない場合**: `+ sword, shield, weapon, holding weapon, holding, holding anything`
- **背景エフェクト不要**: `+ ground, dirt, debris, aura, magic effect, particles, background effects`
- **鎧の顔装飾除去**: `+ face on armor, face on knee, decorative face, mask on armor`
- **リアル調除去**: `+ realistic, photorealistic, 3d render`

### 年齢別タグ
| 年齢帯 | タグ |
|---|---|
| 8歳以下 | child, small child, petite, round face, big round eyes |
| 9-12歳 | child, young girl/boy, petite, round face, big eyes |
| 13-15歳 | young girl/boy, teenager, slim |
| 16-18歳 | teenage girl/boy, teen, slim |
| 成人 | 1girl/1boy, adult |
| 老人 | elderly, old man/woman, wrinkled |

### 種族タグ
| 種族 | タグ |
|---|---|
| 人間 | (なし) |
| エルフ | elf, pointy ears |
| アンデッド | undead, skeleton, skull head, glowing eyes |
| 獣人 | animal ears, tail, fur |
| モンスター | monster, creature, 1other |

### プロンプト長
- キャラデザ探索: **15-25タグ**（短い方が制御しやすい）
- トークン数が増えると個々のキーワードの影響力が薄まる

### 装備・鎧の記述テンプレート
全身鎧を確実に出すための記述パターン（骸骨騎士で実証済み）:
```
full plate armor covering entire body, continuous armor with no gaps,
pauldrons, breastplate, fauld covering abdomen, cuisses, greaves, sabatons
```

装飾:
```
gold ornamental trim, gold filigree on armor edges, golden eagle emblem on breastplate, polished gold accents
```

破損・経年表現:
```
slightly weathered     → 軽い使用感
dirty, rusted, worn    → 標準的な傷み
heavily rusted, corroded, pitted metal → 重度の錆
ancient, decaying, moss-covered → 超古代
```

### 親しみやすいキャラクターの表現
骸骨など本来怖いキャラを親しみやすく描くテンプレート（実証済み）:
```
friendly looking skull, gentle tilted head, soft glowing blue eyes, welcoming posture
curious head tilt, one hand raised in small wave
hands behind back, relaxed casual stance
```

## 実行手順

### Step 1: キャラ設定を解析
- ユーザーの自然言語記述からキャラ属性を抽出
- 不明な点があればユーザーに確認
- 物理的整合性チェック（ベール+髪型、全身鎧の隙間等）

### Step 2: プロンプト生成
- 上記ルールに従ってプロンプトを生成
- 1キャラにつき以下のバリエーションを自動生成:
  - ベースライン (正面全身)
  - 外見バリエーション 2-3種 (キャラに合うもの)
  - 表情・ポーズバリエーション 2-3種
  - 衣装・装備バリエーション 1-2種
  - LoRA有無比較 1枚
  - seed変え 5-8パターン
- ユーザーにプロンプトを提示して確認

### Step 3: ノートブックに書き込み
- `notebooks/char_design_batch/train.ipynb` の **cell-3** を更新
- EXPERIMENTS 配列にキャラ定義を追加
- txt2img と img2img の2つのワークフロー関数を使い分ける

**txt2img (デザイン探索):**
```python
make_hiresfix_workflow(positive, negative, seed, ...)
```

**img2img (画風統一・デフォルメ化):**
```python
make_img2img_workflow(positive, negative, seed, ref_image_path, denoise=0.65, ...)
```

共通デフォルト値:
```python
for exp in EXPERIMENTS:
    exp.setdefault('steps', 28)
    exp.setdefault('sampler', 'euler_ancestral')
    exp.setdefault('scheduler', 'normal')
    exp.setdefault('clip_skip', 2)
    exp.setdefault('lora', LORA_NAME)
    exp.setdefault('lora_w', 0.9)
    exp.setdefault('w', 864)
    exp.setdefault('h', 1152)
    exp.setdefault('hires_scale', 1.5)
    exp.setdefault('hires_steps', 15)
    exp.setdefault('hires_denoise', 0.45)
```

**重要**: cell-0, cell-1, cell-2, cell-4, cell-5, cell-6 は変更しない。cell-3 のみ更新する。

### Step 4: ユーザーに実行を依頼
```
ノートブック更新完了！
Kaggle で T4 を選択して Run All してください。
完了したら character_designs.zip をダウンロードして教えてください。
```

### Step 5: 結果の展開
ユーザーがzipをダウンロードしたら:
```python
import zipfile, os
from datetime import datetime

date_str = datetime.now().strftime('%Y%m%d_%H%M')
out_dir = f'output/char_designs/{date_str}_{キャラ名}'
os.makedirs(out_dir, exist_ok=True)

zpath = 'ユーザー指定のパス'
with zipfile.ZipFile(zpath, 'r') as z:
    z.extractall(out_dir)
```

### Step 6: 後続フェーズへの引き渡し
デザイン確定後、ユーザーに後続作業を提案:
- **nano banana / GPT / Gemini** に確定画像を渡して細部調整
- **img2img** で他キャラと画風統一（denoise 0.6-0.7推奨）
- **GPT / Gemini** でターンアラウンド（正面+背面）生成
- **Gemini** でパーツ分解（透過PNG、ボーンアニメ用）
- **Gemini** で攻撃モーション+武器パーツ+シルエットガイド生成

## ノートブック構成

`notebooks/char_design_batch/train.ipynb`:

| Cell | 内容 | 編集 |
|---|---|---|
| cell-0 | タイトル (markdown) | 触らない |
| cell-1 | GPU Check + ComfyUI install | 触らない |
| cell-2 | モデルリンク + ComfyUI起動 | 触らない |
| **cell-3** | **EXPERIMENTS定義 + ワークフロー関数** | **ここだけ編集** |
| cell-4 | 生成ループ (ComfyUI API) | 触らない |
| cell-5 | グリッドプレビュー | 触らない |
| cell-6 | ZIP出力 | 触らない |

## 確定パラメータ (変更しない)

| 項目 | 値 | ソース |
|---|---|---|
| Clip skip | 2 | RIN公式 |
| CFG | 5.0 | RIN公式 (範囲3-6) |
| Steps | 28 | RIN公式 (範囲20-40) |
| Sampler | euler_ancestral | RIN公式 + テスト結果 |
| Scheduler | normal | テスト結果 (karras非推奨) |
| 解像度 | 864x1152 | RIN公式 |
| LoRA weight | 0.9 | Derpina公式 (0.8-1.0) |
| HiresFix scale | 1.5x | RIN公式 |
| HiresFix steps | 15 | RIN公式 (10-20) |
| HiresFix denoise | 0.45 | RIN公式 (0.35-0.50) |
| ネガティブ | nsfw,nude必須 | Derpina公式 |

## img2img パラメータ

| 項目 | 値 | 用途 |
|---|---|---|
| denoise 0.45 | 元画像にかなり忠実 | 軽微な画風調整 |
| denoise 0.55 | 構図維持+適度な変更 | 標準的な画風統一 |
| denoise 0.65 | 画風大きく変更+シルエット維持 | デフォルメ化推奨値 |
| denoise 0.75 | 大幅変更 | ちび化等 |
| denoise 0.85 | ほぼ新規生成 | 参考程度 |

## 実証済みキャラクター

### シスター (10歳, 金髪, 修道服)
- txt2img → 50+枚探索 → nano banana仕上げ → パーツ分解
- お気に入り: `output/char_designs/fav/`

### 骸骨騎士 (白銀鎧, 金装飾, 白マント)
- txt2img → 60+枚 (v1-v5) → nano banana仕上げ → img2imgデフォルメ化
- GPTターンアラウンド → Geminiパーツ分解+攻撃モーション
- お気に入り: `output/char_designs/fav/騎士/`

## 注意事項
- ComfyUI on Kaggle T4: HiresFix付きで1枚約60-90秒
- 20枚で約20-30分、Kaggle GPU制限は週30時間
- cell-3のみ編集。他のセルは安定版なので触らない
- **diffusersはIllustrious系モデルに使えない** — ComfyUIが唯一の正常動作環境
- プロンプトのTips参照: `docs/wiki/キャラクター画像_プロンプトTips.md`
- リサーチドキュメント: `designs/game-image-gen-agent-research.md`
