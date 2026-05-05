---
name: create-balance-sheet
description: Create game balance data sheets (enemy stats, item tables, drop rates, etc.) as CSV/Excel for easy human editing.
user-invocable: true
argument-hint: <data type> [enemies|items|weapons|skills|stages|custom]
---

# Create Balance Sheet: $ARGUMENTS

ゲームバランスデータをCSV/Excelで作成する。人間が編集しやすいスプレッドシート形式。

## 対応データ種別

### enemies — 敵パラメータ
```csv
ID,名前,HP,攻撃力,防御力,速度,行動パターン,ドロップアイテム,ドロップ率,出現ステージ,備考
```

### items — アイテム
```csv
ID,名前,種別,効果,値,スタック上限,入手方法,レアリティ,備考
```

### weapons — 武器
```csv
ID,名前,種別,攻撃力,射程,速度,消費リソース,特殊効果,備考
```

### skills — スキル/アビリティ
```csv
ID,名前,種別,効果,消費コスト,クールダウン,習得条件,備考
```

### stages — ステージ難易度
```csv
ID,ステージ名,推奨レベル,敵構成,ギミック,推定クリア時間,難易度,報酬,備考
```

### custom — カスタム
ユーザーの指定に応じて任意のデータ構造で作成。

## 手順

1. **GDD参照**: `designs/game-design.md` と関連システム設計書を読み、ゲームの文脈を理解
2. **asset-spec.json参照**: ワールド設定（プレイヤーHP、攻撃力基準等）を確認
3. **バランス設計**: ジャンルの定番バランスを参考に初期値を設定
   - 難易度カーブ: 序盤は易しく、徐々に上昇
   - パワーカーブ: プレイヤーの成長に合わせた敵の強さ
4. **CSV/Excel出力**: `designs/balance/` ディレクトリに出力
5. **ユーザー確認**: 値の調整をユーザーと対話で行う

## バランス設計の原則

- **プレイヤーHP基準**: プレイヤーHPを100として、敵の攻撃力を割合で設定
- **3ヒットルール**: 雑魚敵は3回攻撃で倒せるのが基本
- **ボスは10-15ヒット**: ボスは長めの戦闘を想定
- **回復アイテム**: プレイヤーHP の 20-30% 回復が基本
- **難易度倍率**: ステージが進むごとに 1.2-1.5倍 の増加

## 出力先
- `designs/balance/[データ種別].csv`
- または `designs/balance/[データ種別].xlsx`（Excel形式が必要な場合）

## ScriptableObject連携

CSV/Excelで確定したデータは、対応するScriptableObjectに反映する:
- 手動: Inspectorで値を入力
- 自動: CSVインポーターEditorスクリプトを作成（必要に応じて）
