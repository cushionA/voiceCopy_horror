# voiceCopy_horror

> 一人称ホラー FPS — プレイヤーの**声**でゲームの結末が変わる
> Unity + UHFPS テンプレート + Qwen3-TTS

---

## 🎮 ゲーム概要

夜の洋館に閉じ込められた主人公が、3 人の子供幽霊から逃げる一人称ホラー。
**プレイヤーが実際に声を出すと敵が強化** され、**最後に録音した声の類似度** でエンディングが分岐する。

| 要素 | 仕様 |
|---|---|
| ジャンル | 一人称ホラー FPS |
| プラットフォーム | Steam（PC） |
| エンジン | Unity 6 + URP |
| ベース | UHFPS テンプレート（ThunderWire Studio） |

### コアメカニクス
- **3 体の幽霊**: マギー（臆病）/ アルフレッド（勇敢）/ マークス（賢い）
- **攻略**: 各幽霊 4 文書（計 12 個）を読み切ると攻撃が通じる
- **ボイス強化**: マイク入力で敵が強化（時間で半減）
- **推理パズル**: 死因と性格・外傷の照合
- **少女幽霊**: 電話越しに指示を出す味方（Qwen3-TTS で動的生成）
- **エンディング分岐**: 全プレイ中の録音と少女の声の類似度で結末が変わる

---

## 🛠 技術スタック

| カテゴリ | 採用技術 | ライセンス |
|---|---|---|
| ゲームエンジン | Unity 6 (URP) | プロプライエタリ |
| FPS テンプレート | UHFPS by ThunderWire Studio | 有料アセット（**リポジトリには含めない**） |
| TTS | Qwen3-TTS-12Hz-1.7B-Base | Apache 2.0 |
| ComfyUI 統合 | TTS-Audio-Suite (diodiogod) | MIT |
| 開発ハーネス | Claude Code | - |

---

## 📁 ディレクトリ構成

```
voiceCopy_horror/
├── .claude/                 # Claude Code 設定（rules, skills, hooks, agents）
├── designs/                 # パイプライン状態スキーマ
├── docs/
│   ├── UHFPS_Inventory.md   # UHFPS 機能棚卸し（コアメカニクス対応マップ）
│   └── FUTURE_TASKS.md      # 派生タスク
├── instruction-formats/     # 各種フォーマット定義
├── scripts/                 # セッション初期化スクリプト
├── tools/                   # feature-db / lint / cost / 他ユーティリティ
├── voiceCoppy_test/         # TTS 検証ワークフロー JSON + サンプル音声
└── voice_Horror_Game/       # Unity プロジェクト本体
    ├── Assets/
    │   ├── Scenes/
    │   ├── Settings/
    │   └── ThunderWire Studio/
    │       └── UHFPS/       # ★ 有料アセット、git 除外（要購入）
    ├── Packages/
    └── ProjectSettings/
```

---

## 🚀 セットアップ手順

### 1. リポジトリをクローン

```bash
git clone https://github.com/cushionA/voiceCopy_horror.git
cd voiceCopy_horror
```

### 2. UHFPS テンプレートを導入（要購入）

UHFPS は **有料アセット** のためリポジトリに含まれていません。
[Unity Asset Store](https://assetstore.unity.com/) から購入アカウントで取得し、以下のパスに配置してください:

```
voice_Horror_Game/Assets/ThunderWire Studio/UHFPS/
```

`docs/UHFPS_Inventory.md` に UHFPS 機能とプロジェクト機能の対応マップを記載しています。

### 3. Unity プロジェクトを開く

- Unity 6 (URP) で `voice_Horror_Game/` を開く
- 初回は Library/ の再生成 + UHFPS の import で時間がかかります

### 4. TTS 環境（音声機能用、開発時のみ）

ComfyUI Desktop と TTS-Audio-Suite カスタムノードが必要です:

| 項目 | 値 |
|---|---|
| ComfyUI パス | `C:\Users\<user>\Documents\ComfyUI\` |
| カスタムノード | `ComfyUI/custom_nodes/TTS-Audio-Suite/` |
| ワークフロー | `voiceCoppy_test/japanese_clone_test_qwen3.json` |
| サンプル音声 | `voiceCoppy_test/my_sampleVoice.wav` |
| 推奨 GPU | RTX 2070 Super 8GB VRAM 以上 |

---

## 📜 ライセンス

| 内容 | ライセンス |
|---|---|
| 本リポジトリのソースコード・ドキュメント | （未定。プロジェクト着手時点では未公開のため、利用許諾は別途） |
| UHFPS アセット | ThunderWire Studio 有料ライセンス（**再配布禁止**、含まれていません） |
| Qwen3-TTS モデル | Apache 2.0 |
| `.claude/refs/external/nice-wolf-studio/` | MIT（出典明記、`_attribution.md` 参照） |

UHFPS / ComfyUI モデルウェイト / API キー / 録音データは **絶対に commit しないでください**（`.gitignore` で除外済み）。

---

## 📚 詳細ドキュメント

| ファイル | 内容 |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | プロジェクト全体ガイド、音声システム、ライセンス判断、作業ルール |
| [`docs/UHFPS_Inventory.md`](docs/UHFPS_Inventory.md) | UHFPS 機能棚卸し × ゲームメカニクス対応マップ |
| [`.claude/rules/`](.claude/rules/) | コード規約、Git 運用、TDD、セキュリティ等 |

---

## 🤝 開発体制

- **個人開発**（Claude Code 補助）
- TDD ワークフロー（`tools/feature-db.py` でテスト記録）
- Git コミット規約: `[種類](範囲): 日本語タイトル`
