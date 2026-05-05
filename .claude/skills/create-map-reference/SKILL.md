---
name: create-map-reference
description: Create an interactive HTML reference map for stage/level design. Human uses this as a visual guide for building stages.
user-invocable: true
argument-hint: <stage theme/concept description>
---

# Create Map Reference: $ARGUMENTS

ステージ設計のリファレンスとなるインタラクティブHTMLマップを作成する。
**人間がステージを構築する際のガイド**として使う。AIがステージを自動構築するためのものではない。

## 手順

1. **コンセプト理解**: ユーザーのステージテーマ・コンセプトを把握
2. **GDD参照**: `designs/game-design.md` からゲームのメカニクスを確認
3. **asset-spec.json参照**: ワールド設定（タイルサイズ、ジャンプ距離等）を確認
4. **既存ノート参照**: `designs/stage-design-notes.md` から過去の学習を確認
5. **ギミックレジストリ参照**: `designs/gimmick-registry.json` から成功パターンを確認
6. **HTMLマップ作成**: Canvas/SVGベースのインタラクティブマップを生成

## HTMLマップの要件

### 必須機能
- ドラッグでスクロール（大きなマップに対応）
- ホイールでズーム
- ホバーでエンティティ情報表示
- エリア名・セクション名の表示
- 凡例（タイル種別、エンティティ種別）

### 含める情報
- **地形構造**: 床、壁、天井、プラットフォーム
- **ギミック配置**: スイッチ、ドア、エレベーター、ワープ等
- **敵配置案**: 敵の種類と概略位置
- **アイテム配置案**: 回復、強化、鍵等
- **プレイヤー動線**: 想定される移動ルート
- **チェックポイント**: セーブポイント位置
- **難易度ゾーン**: 区間ごとの難易度目安

### ビジュアルスタイル
- テーマに合った配色（研究施設→暗い青緑、森→緑、火山→赤橙）
- タイルベースのグリッド表示
- アイコンまたは色分けでエンティティを区別

## 出力先
- `designs/map-references/[stage_id].html`

## 注意
- このHTMLはあくまで**設計リファレンス**。Unityシーンを自動生成するものではない
- 人間がこのマップを見ながらUnityエディタでステージを構築する
- AIはMCP経由で構築結果を検証（`/validate-scene`）する補助的役割
