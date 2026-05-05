# Stage Layout 2D 指示フォーマット

このフォーマットを使用して、2Dサイドスクロールステージの構成をAIに指示する。
チャンク単位でステージを定義し、タイルマップ・敵・アイテム・ギミックを配置する。

## 概要
- ステージは水平方向に連続するチャンク（Chunk）で構成される
- 各チャンクは1画面幅相当（16〜20タイル幅 x 12タイル高が推奨）
- タイルグリッドはテキスト文字で表現し、下がY=0、上がY=max
- 座標系: 左下が原点、右がX+、上がY+

## タイル文字一覧

| 文字 | タイル種類 | 説明 |
|------|-----------|------|
| `.` | 空気 (Air) | 何もない空間 |
| `#` | 地面 (Solid) | 固体ブロック、全方向衝突 |
| `=` | プラットフォーム (Platform) | 上から乗れる、下からすり抜け可能 |
| `^` | スパイク (Spike) | 接触でダメージ |
| `~` | 水 (Water) | 水中エリア |
| `>` | 右向きベルト (ConveyorRight) | 右方向に押す床 |
| `<` | 左向きベルト (ConveyorLeft) | 左方向に押す床 |
| `X` | 破壊可能ブロック (Breakable) | 攻撃で壊せるブロック |
| `L` | ハシゴ (Ladder) | 上下移動可能 |
| `|` | 壁 (Wall) | 壁ジャンプ可能面（任意） |

## フォーマット

```
# Stage: [ステージID]

## Meta
- name: [ステージ表示名]
- world: [ワールド番号/名前]
- difficulty: [1-10]
- time_limit: [秒数 or none]
- music: [BGM識別子]
- background: [背景テーマ]

## Tiles
- tile_width: [1タイルのワールド単位サイズ, default: 1]
- tileset: [使用タイルセット名]

## Parallax
- layer0: [最奥背景] (scroll: [0.0-1.0])
- layer1: [中間背景] (scroll: [0.0-1.0])
- layer2: [前景装飾] (scroll: [0.0-1.0])

## Chunks

### Chunk [番号] ([説明])
```
[タイルグリッド: 上の行が高いY座標]
```

#### Enemies
- [敵タイプ] (tile: [col,row]) (behavior: [パターン名]) [追加パラメータ]

#### Items
- [アイテムタイプ] (tile: [col,row])

#### Hazards
- [ハザードタイプ] (tile: [col,row]) [パラメータ]

#### Objects
- [オブジェクトタイプ] (tile: [col,row]) [パラメータ]

### Chunk [次の番号] ([説明])
...

## Special Positions
- spawn: chunk [N] tile [col,row]
- goal: chunk [N] tile [col,row]
- checkpoints:
  - checkpoint_1: chunk [N] tile [col,row]
  - checkpoint_2: chunk [N] tile [col,row]

## Difficulty Parameters
- enemy_density: [low/medium/high]
- platform_gap_max: [最大プラットフォーム間隔タイル数]
- hazard_frequency: [low/medium/high]
- powerup_frequency: [low/medium/high]
- notes: [難易度調整に関する補足]
```

## 敵Behavior一覧

| パターン名 | 説明 |
|-----------|------|
| patrol | 左右に往復歩行 |
| patrol_edge | 足場の端で折り返す |
| chase | プレイヤーを追跡 |
| jump | 定期的にジャンプ |
| fly_horizontal | 水平に飛行往復 |
| fly_sine | サイン波状に飛行 |
| stationary | 移動しない（射撃など） |
| guard | 一定範囲内で待機、接近で攻撃 |

## アイテムタイプ一覧

| タイプ | 説明 |
|--------|------|
| coin | コイン/通貨 |
| health | 回復アイテム |
| powerup_speed | 移動速度アップ |
| powerup_jump | ジャンプ力アップ |
| powerup_attack | 攻撃力アップ |
| key | 鍵（ロック解除用） |
| 1up | 残機追加 |
| secret | 隠しアイテム |

## オブジェクトタイプ一覧

| タイプ | 説明 | パラメータ |
|--------|------|-----------|
| moving_platform | 移動床 | path: [tile座標リスト], speed: [値] |
| spring | バネ（高ジャンプ） | force: [値] |
| door | ドア（鍵で開く） | key_id: [ID] |
| switch | スイッチ | target: [対象オブジェクトID] |
| npc | NPC | dialog: [テキスト] |
| sign | 看板 | text: [テキスト] |
| event_zone | イベントシーン再生領域 | event_id: [イベントID], size: [幅,高さ] |

## 使用例

```
# Stage: stage_1_1

## Meta
- name: 草原の冒険
- world: 1
- difficulty: 2
- time_limit: 300
- music: bgm_world1
- background: grassland

## Tiles
- tile_width: 1
- tileset: grassland_tiles

## Parallax
- layer0: sky_gradient (scroll: 0.1)
- layer1: distant_mountains (scroll: 0.3)
- layer2: near_trees (scroll: 0.7)

## Chunks

### Chunk 0 (スタートエリア — 平坦で安全)
```
....................
....................
....................
....................
....................
....................
....................
....................
....................
####################
####################
####################
```

#### Items
- coin (tile: 5,3)
- coin (tile: 7,3)
- coin (tile: 9,3)

### Chunk 1 (最初のプラットフォーム)
```
....................
....................
....................
..........====......
....................
....................
....====............
....................
....................
########....########
####################
####################
```

#### Enemies
- slime (tile: 2,3) (behavior: patrol_edge)

#### Items
- coin (tile: 12,7)
- coin (tile: 13,7)
- health (tile: 14,7)

### Chunk 2 (敵とハザード導入)
```
....................
....................
....................
....................
..............====..
....................
....................
....====............
..........^^........
####################
####################
####################
```

#### Enemies
- flying_enemy (tile: 10,6) (behavior: fly_sine)

#### Hazards
- spike_pit (tile: 10,3) (width: 2)

#### Objects
- moving_platform (tile: 6,5) path: [6,5 -> 14,5] speed: 2

### Chunk 3 (ゴールエリア)
```
....................
....................
....................
....................
....................
....................
....................
....................
....................
####################
####################
####################
```

#### Objects
- sign (tile: 16,3) text: "ゴール！"

## Special Positions
- spawn: chunk 0 tile 3,3
- goal: chunk 3 tile 18,3
- checkpoints:
  - checkpoint_1: chunk 1 tile 10,3

## Difficulty Parameters
- enemy_density: low
- platform_gap_max: 4
- hazard_frequency: low
- powerup_frequency: medium
- notes: 初めてのステージ。操作練習を兼ねる。敵は弱いスライムのみ。
```

## 注意事項
- タイルグリッドの行数は全チャンクで統一すること（高さが異なるとビルド時にずれる）
- タイルグリッドの列数は全チャンクで統一すること（チャンク幅の基準）
- グリッド内の `tile: col,row` 指定は0始まり、左下原点（表示上はグリッドの最下行がrow=0）
- 敵・アイテムの座標はタイルグリッド座標で指定（ワールド座標への変換はStageBuilderが行う）
- チャンクは番号順に左から右へ水平に連結される
- `[PLACEHOLDER]` ルールは通常通り適用：タイルセットやスプライトが未準備の場合はプレースホルダーカラーブロックで構築
