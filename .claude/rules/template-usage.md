---
description: Rules for selecting and customizing GameObject templates
---

# テンプレート使用規約

## テンプレート選択手順
1. GameObjectを新規作成する前に `unity-bridge/Templates/template-registry.json` を確認
2. 該当するテンプレートがあれば、それを基にPrefab Variantを作成する
3. テンプレートにない場合のみゼロから作成し、汎用性があればテンプレート化を検討

## template-registry.json の参照方法
- `use_when` フィールドで適用条件を判断
- `customizable_properties` フィールドで変更可能なプロパティを確認
- テンプレートの構成を変更する場合は、Prefab Variantとして派生させる

## テンプレートの追加基準
- 2回以上同じ構成のGameObjectを作る場合はテンプレート化する
- テンプレート追加時は `template-registry.json` も更新する

## カスタマイズ方針
- コンポーネントの追加: 自由に追加可能
- コンポーネントの削除: Prefab Variantでは非推奨。新テンプレート作成を検討
- プロパティ変更: `customizable_properties` に記載されたものを優先変更
