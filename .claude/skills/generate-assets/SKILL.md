---
name: generate-assets
description: ダミーアセット自動生成（画像はKaggle SD 1.5、音声は手持ちライブラリからマッチング）。pendingアセットを一括処理する。音声インデックスの管理（旧 index-assets）も内包。
user-invocable: true
argument-hint: [images|audio|fetch|index <build|update|search|stats>]
---

# Generate Assets: $ARGUMENTS

pendingアセットの自動生成・マッチングと、音声アセットライブラリのインデックス管理を行う。

旧 `/index-assets` スキルは本スキルの `index` サブコマンドに統合された（2026-04-24）。

## サブコマンド

### 引数なし or `all` — 画像生成+音声マッチング

1. `python tools/feature-db.py assets --status pending` でpendingアセット一覧を取得
2. アセットをタイプ別に振り分け:
   - **Sprite/Texture/Image** → 画像生成フロー（再利用チェック込み）
   - **Audio/SFX/BGM** → 音声マッチングフロー（再利用チェック込み）
   - **その他** → スキップ（手動対応が必要）
3. それぞれのフローを実行
4. 結果レポートを出力

### `images` — 画像のみ

#### 手順

1. `python tools/generate-images.py prepare` を実行
   - **再利用チェックが自動実行される**: 既存ファイル、同じdescriptionのplaced済みアセット、同名ファイルを検出
   - 再利用可能なアセットは生成対象から除外され、レポートに表示される
   - 特定のアセットIDのみ: `python tools/generate-images.py prepare --asset-ids A001 A002`
2. 出力を確認:
   - 再利用可能アセットがあれば、ユーザーにコピー&bind実行を提案
   - 新規生成が必要なアセットがあれば `designs/asset-gen-request.json` の内容を提示
3. ユーザー承認後:
   - 再利用アセット: 既存ファイルを `expected_path` にコピー → `feature-db bind` 実行
   - 新規生成: `python tools/generate-images.py submit` を実行
4. Kaggle kernelが実行される旨をユーザーに通知
5. 「`/generate-assets fetch` で結果を取り込めます」と案内

### `audio` — 音声のみ

#### 手順

1. **インデックス確認**: `config/audio-index.json` が存在するか確認
   - 存在しない → `python tools/asset-index.py build` を自動実行してインデックス作成
   - 存在する → そのまま使用（必要なら `python tools/asset-index.py update` で差分更新）
2. `python tools/feature-db.py assets --status pending` からAudio系アセットを抽出
3. **再利用チェック**: 各pendingアセットについて:
   - `expected_path` に既にファイルが存在するか確認
   - 同じdescriptionで既にplacedの音声アセットがあるか確認（feature-db参照）
   - 再利用可能なら生成対象から除外し、既存ファイルをコピー → bind
4. 新規マッチングが必要なアセットのみ、descriptionをもとにインデックス検索:
   - `python tools/asset-index.py search "<description keywords>"` を実行
5. 検索結果からLLMが最適な候補を選定（ファイル名、フォルダ名、サイズから判断）
   - **同じ音声を複数箇所で使える場合は積極的に再利用する**
   - 一度選定した音声ファイルは、類似descriptionの他のアセットにも提案する
6. 候補をユーザーに提示（アセットID、元の説明、選定候補、選定理由）
7. ユーザー承認後:
   - 音声ファイルをUnityプロジェクトの `Assets/Audio/` にコピー
   - `python tools/feature-db.py bind <asset_id>` で配置済みに更新
8. 結果レポート出力

### `fetch` — Kaggle結果取り込み

1. `python tools/generate-images.py status` で状態確認
2. 完了していれば `python tools/generate-images.py fetch` を実行
3. 配置結果を報告

### `index <サブコマンド>` — 音声インデックス管理（旧 `/index-assets`）

音声ライブラリ（`config/asset-gen.json` の `audio_libraries`）のインデックスを管理する。
`audio` サブコマンドで初回インデックス構築は自動だが、差分更新・検索・統計は本サブコマンドで明示実行する。

#### `index build` — フルスキャン

1. `config/asset-gen.json` の `audio_libraries` を確認
2. パスが存在しない場合はユーザーに修正を案内
3. `python tools/asset-index.py build` を実行
4. 結果を報告（ファイル数、ライブラリ数）

#### `index update` — 差分更新

1. `python tools/asset-index.py update` を実行
2. 追加・削除されたファイル数を報告

#### `index search <query>` — 検索+候補提示

1. `python tools/asset-index.py search "<query>"` を実行
2. ツール出力のJSON候補リストを評価
3. feature-dbのpending assetsのDescriptionと照合
4. 最も適切な候補を理由付きで提示
5. ユーザーが承認したら、そのファイルをUnityプロジェクトの`Assets/`にコピーする手順を案内

#### `index stats` — 統計表示

1. `python tools/asset-index.py stats` を実行
2. 結果をそのまま表示

#### 検索のコツ

- 日本語キーワードとファイル名（通常英語）の両方で検索
- 「ジャンプSE」→ `jump sound effect short` のように英語キーワードも試す
- フォルダ名でカテゴリを絞り込む: `Action jump`, `UI click`

## 前提条件

- `config/asset-gen.json` が設定済みであること
- 画像生成: Kaggle APIが設定済み（`kaggle.json`）
- 音声マッチング: `config/audio-index.json` が作成済み（`/generate-assets index build` で作成）
- feature-dbが初期化済みで、pendingアセットが登録されていること

## 注意事項

- 画像生成はKaggle GPUを使用するため、実行時間は数分〜十数分
- 音声マッチングはローカルで即時実行
- 生成された画像はプレースホルダーの代替であり、最終品質ではない
- 音声はファイル名・フォルダ名ベースのマッチングのため、実際に聴いて確認を推奨
