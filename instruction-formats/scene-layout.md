# Scene Layout 指示フォーマット

このフォーマットを使用して、シーン内のGameObject配置をAIに指示する。

## フォーマット

```
# Scene: [シーン名]

## Environment
- [GO名] (position: x,y,z) (rotation: x,y,z) (scale: x,y,z)
  - Components: [コンポーネント1], [コンポーネント2]
  - Properties:
    - [コンポーネント名].[プロパティ名] = [値]
  - Children:
    - [子GO名] (position: x,y,z)
      - Components: [コンポーネント1]

## Characters
- [GO名] (template: [テンプレート名]) (position: x,y,z)
  - Override:
    - [プロパティ名] = [値]

## UI
- Canvas (render mode: [ScreenSpaceOverlay|ScreenSpaceCamera|WorldSpace])
  - [UIフォーマット参照]

## Lighting
- [ライト名] (type: [Directional|Point|Spot]) (position: x,y,z)
  - color: [r,g,b]
  - intensity: [値]
  - shadows: [None|Hard|Soft]

## Camera
- Main Camera (position: x,y,z) (rotation: x,y,z)
  - projection: [Perspective|Orthographic]
  - size/fov: [値]
```

## 使用例

```
# Scene: Level_01

## Environment
- Ground (position: 0,0,0) (scale: 50,1,50)
  - Components: BoxCollider, MeshRenderer
  - Properties:
    - MeshRenderer.material = Materials/Ground_Grass

- Wall_North (position: 0,1,25) (scale: 50,3,1)
  - Components: BoxCollider, MeshRenderer

## Characters
- Player (template: Character3D) (position: 0,1,0)
  - Override:
    - moveSpeed = 5.0
    - jumpForce = 8.0

- [PLACEHOLDER]Enemy_Patrol (position: 10,1,5)
  - Components: Rigidbody, CapsuleCollider, EnemyAI
  - Properties:
    - EnemyAI.patrolRadius = 5.0

## Lighting
- Sun (type: Directional) (rotation: 50,-30,0)
  - color: 1.0, 0.95, 0.9
  - intensity: 1.2
  - shadows: Soft

## Camera
- Main Camera (position: 0,10,-10) (rotation: 45,0,0)
  - projection: Perspective
  - fov: 60
```

## 注意事項
- `template:` 指定時は template-registry.json のテンプレートを使用
- `[PLACEHOLDER]` プレフィックス付きGOは仮素材として作成
- position/rotation/scale は省略時デフォルト値 (0,0,0)/(0,0,0)/(1,1,1)
- Children はインデントで階層を表現
