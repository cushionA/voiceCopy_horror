---
description: Unity C# coding conventions and component design rules
---

# Unity コード規約

## 原則
- **KISS**: 可能な限りシンプルな解決策を選ぶ
- **YAGNI**: 現在必要な機能のみを実装する
- **DRY**: コードの重複を避ける
- **問題の根本原因を特定する**: 応急処置ではなく根本的な解決を図る

## 命名規則

### ケーシング

| 対象 | スタイル | 例 |
|------|---------|-----|
| クラス名 | PascalCase | `PlayerMovement` |
| インターフェース | I + PascalCase | `IDamageable` |
| メソッド名 | PascalCase | `CalculateDistance()` |
| プロパティ | PascalCase | `MaxHealth` |
| public フィールド | PascalCase | `MovementSpeed` |
| ローカル変数・引数 | camelCase | `moveDirection` |
| privateフィールド | _camelCase | `_currentHealth` |
| 定数 (const) | k_ + PascalCase | `k_MaxSpeed` |
| SerializeField | camelCase | `[SerializeField] private float moveSpeed` |
| enum 名 | PascalCase (単数形) | `WeaponType` |
| enum フラグ | PascalCase (複数形) | `[Flags] AttackModes` |
| 名前空間 | PascalCase | `MyGame.PlayerSystems` |

### 命名の原則
- 変数名は名詞: `playerScore`, `targetObject`
- bool値は動詞で始める: `isAlive`, `hasWeapon`, `canJump`
- メソッド名は動詞: `FireWeapon()`, `CalculateDistance()`
- boolを返すメソッドは疑問文: `IsPlayerAlive()`, `HasAmmo()`
- イベント名は動詞句: `PointsScored`, `DoorOpened`
- イベント発生メソッドは "On" で始める: `OnDoorOpened()`
- 特殊文字・略語は避ける（数学的表現やループカウンタを除く）

## コンポーネント設計
- 1コンポーネント = 1責務（Single Responsibility）
- publicフィールドではなく `[SerializeField] private` を使用
- Inspector設定値は `[Header("Section")]` でグループ化
- `RequireComponent` 属性で依存コンポーネントを明示
- `GetComponent` 呼び出しは `Awake`/`Start` でキャッシュ

## クラス構成順序
1. Fields
2. Properties
3. Events / Delegates
4. MonoBehaviour Methods (Awake, Start, OnEnable, etc.)
5. Public Methods
6. Private Methods

## ファイル構成
- 1ファイル = 1クラス
- ファイル名 = クラス名
- Editor専用スクリプトは `Editor/` フォルダに配置
- テストは `Tests/EditMode/` または `Tests/PlayMode/` に配置

## マジックナンバー禁止
```csharp
// NG
transform.position += Vector3.up * 9.81f * Time.deltaTime;

// OK
private const float k_Gravity = 9.81f;
transform.position += Vector3.up * k_Gravity * Time.deltaTime;
```

## MonoBehaviour ライフサイクル順序
1. Awake() — コンポーネント参照の取得
2. OnEnable() — イベント登録
3. Start() — 初期化ロジック
4. Update/FixedUpdate — 毎フレーム処理
5. OnDisable() — イベント解除
6. OnDestroy() — リソース解放

## フォーマット
- インデント: スペース4つ（タブ不使用）
- 中括弧: Allman スタイル（新しい行に開き括弧）
- `csharp_prefer_braces = true`（1行でも中括弧を付ける）
- `var` は使用しない（型を明示）

## パフォーマンス規約

### Update内のアロケーション禁止
```csharp
// NG: 毎フレームでアロケーション
void Update()
{
    List<GameObject> tempList = new List<GameObject>();
}

// OK: フィールドで事前確保して再利用
private List<GameObject> _reusableList = new List<GameObject>();
void Update()
{
    _reusableList.Clear();
}
```

### 文字列連結の最適化
- Update内での `string +` 連結禁止
- `StringBuilder` またはキャッシュを使用

### GetComponent呼び出しの最小化
- 初期化時（Awake/Start）にキャッシュ
- `transform` プロパティもキャッシュ推奨

### 距離計算の最適化
- `Vector3.Distance` の代わりに `sqrMagnitude` 比較を検討
- 範囲値も2乗でキャッシュ

### タグ比較
- `obj.tag == "Player"` ではなく `obj.CompareTag("Player")` を使用

### enum型の最適化
- 値が少ない場合は `byte` 型指定でメモリ節約
- 4つ以上の条件分岐では `switch` 文推奨

### 条件コンパイル
```csharp
#if UNITY_EDITOR
    // エディター専用デバッグ処理
#endif

[System.Diagnostics.Conditional("UNITY_EDITOR")]
void DebugLog(string message)
{
    Debug.Log(message); // リリースビルドでは完全に除去
}
```

## コメント規約
- コードが自明でない場合のみ使用
- 「何を」ではなく「なぜ」を説明
- `[Tooltip("説明")]` でInspectorのヒントを付与
- XML ドキュメント (`/// <summary>`) は公開APIに付与

---

# 実行時バグ防止パターン

以下は規約 regex で検出しづらいが「**実行時に確実にバグになる**」 Unity 固有の罠。
コードレビュー時に必ず確認すること。

> Sources: nice-wolf-studio/unity-claude-skills (MIT) — unity-lifecycle / unity-physics-queries / unity-async-patterns / unity-foundations / unity-scripting / unity-performance

## ライフサイクル罠

### Fake-null trap: `?.` / `??` / `is null` を Unity Object に使わない
Unity は `==` 演算子をオーバーライドして「破棄済みオブジェクト」を null として扱うが、C# native の null チェック（`?.`、`??`、`is null`、`is not null`、パターンマッチ `obj is MyType t`）は**このオーバーライドをバイパスする**。`MissingReferenceException` の最大原因。

```csharp
// NG: 破棄済みオブジェクトでメソッド呼び出される可能性
myComponent?.DoSomething();
var fallback = myComponent ?? other; // fake-null が返る

// OK: == null か暗黙 bool 変換を使う
if (myComponent != null) myComponent.DoSomething();
if (myComponent) myComponent.DoSomething();
```

### `Destroy()` は遅延破棄
`Destroy(obj)` はフレーム終端で実行される。**同フレームで `== null` チェックは true を返す**が、`OnDisable`/`OnDestroy` は遅れて実行される。`DestroyImmediate` はランタイム禁止（Editor 専用）。

```csharp
// NG: コレクション反復中の Destroy で破壊
foreach (var e in enemies)
    if (e.health <= 0) Destroy(e.gameObject);

// OK: 一旦リストに集めてから
var toDestroy = enemies.Where(e => e.health <= 0).ToList();
foreach (var e in toDestroy) { enemies.Remove(e); Destroy(e.gameObject); }
```

### Awake は GameObject 単位、Start/OnEnable は Component 単位
- `Awake`: **GameObject** が active なら、Component が disabled でも実行される
- `Start`: **Component** が enabled でない限り実行されない（後で enable された時点で発火）
- `OnEnable` / `OnDisable`: イベント subscribe/unsubscribe の正典ペア

### `OnEnable` / `OnDisable` でイベント subscribe/unsubscribe の対称性
`Start`/`OnDestroy` で組むと **オブジェクトプール / DontDestroyOnLoad / シーン再ロード**で破綻する。

```csharp
void OnEnable()  { EventManager.OnPlayerDied += HandlePlayerDied; }
void OnDisable() { EventManager.OnPlayerDied -= HandlePlayerDied; }
```

### `OnValidate` は Editor 専用、ビルドから除去される
ランタイム初期化を `OnValidate` に書くと**ビルドで実行されない**。Inspector 値クランプ用途のみ、`#if UNITY_EDITOR` で囲む。

### `OnApplicationQuit` を保存処理に使う
`OnDestroy` の実行順は不定なので、保存処理は他オブジェクトがまだ生きている `OnApplicationQuit` が安全。モバイルでは発火しないことがあるため `OnApplicationPause(true)` も併用。

### スクリプト実行順序
同コールバック間の実行順は**非決定論的**。「Awake = 自己初期化、Start = 他オブジェクト参照」の Pattern を守れば安全。明示制御は `[DefaultExecutionOrder(-100)]` 属性。

### `[ExecuteAlways]` は Edit mode で `Update` がフレームごとに呼ばれない
Scene view 再描画時のみ実行される。`Time.deltaTime` も信頼できない。`Application.isPlaying` で分岐する。

### `[RuntimeInitializeOnLoadMethod]` のデフォルトは `AfterSceneLoad`
最初の Awake より**後**に実行される。早期に走らせたい場合は明示指定:
- `SubsystemRegistration` — domain reload 完了前（static 状態クリア用）
- `BeforeSceneLoad` — 最初の Awake より前
- `AfterAssembliesLoaded`、`BeforeSplashScreen` も指定可

### async + 破棄: `destroyCancellationToken` 必須
詳細は次節「async/await 致命罠」を参照。

---

## 物理クエリ規約

### NonAlloc 必須（GC 圧削減）
ホットパスの物理クエリは `NonAlloc` 系を使う。バッファはフィールドで事前確保し、**返り値の count までしか反復しない**。

```csharp
// フィールドで事前確保（再利用）
private readonly RaycastHit[] _hitBuffer = new RaycastHit[16];

void DetectHits()
{
    int count = Physics.RaycastNonAlloc(ray, _hitBuffer, maxDist, layerMask);
    for (int i = 0; i < count; i++) ProcessHit(_hitBuffer[i]);

    if (count == _hitBuffer.Length)
        AILogger.Log("Hit buffer 満杯、結果欠落の可能性"); // バッファサイズ調整シグナル
}
```

GC アロケーションパターン: `Raycast` 単発以外は基本 NonAlloc 系（`RaycastNonAlloc` / `OverlapSphereNonAlloc` / `SphereCastNonAlloc` 等）。

### クエリ種別の選択
| 用途 | API |
|---|---|
| 「何かある？」(bool 判定) | `CheckSphere` / `CheckBox` / `CheckCapsule`（最速）|
| 線上で最も近い 1 つ | `Raycast`（closest 自動）|
| 体積を sweep して最も近い 1 つ | `SphereCast` / `BoxCast` / `CapsuleCast` |
| 線上の全部 | `RaycastAll` / `RaycastNonAlloc`（**ソートされない**）|
| 領域内の全部 | `OverlapSphere` / `OverlapBox` / `OverlapCapsule` |

`RaycastAll` / `*NonAlloc` 系の結果は**距離順にソートされていない**。距離順が必要なら `Array.Sort` で手動ソート。

### Cast 起点が collider 内側にあると検出失敗
Cast 系は**起点が collider 内部の場合、その collider を無視する**。地面チェックの典型バグ。「現在何に触れているか」は `Overlap*` / `Check*` を使う。

```csharp
// NG: SphereCast 起点が地面 collider 内に入ると検出 miss
Physics.SphereCast(feetPosition, radius, Vector3.down, out hit, 0.1f, groundMask);

// OK: 現在重なり判定は CheckSphere / OverlapSphere
grounded = Physics.CheckSphere(feetPosition, radius, groundMask);
```

### LayerMask の bitshift と GetMask の混同
- `LayerMask.GetMask("Ground")` → **bitmask**（例: 256）
- `LayerMask.NameToLayer("Ground")` → **layer index**（例: 8）
- `gameObject.layer` → **index**

```csharp
// NG: 二重シフト
int mask = 1 << LayerMask.GetMask("Ground"); // bitmask をさらに左シフト = 大量にずれる

// OK
int groundMask = LayerMask.GetMask("Ground");
int multiMask = LayerMask.GetMask("Ground", "Water");
int everythingButGround = ~LayerMask.GetMask("Ground");
```

### `QueryTriggerInteraction` のデフォルトは UseGlobal = trigger を含む
明示的に `Ignore` を指定するか、ヒット後 `!hit.collider.isTrigger` でフィルタする。地面チェック / 視線判定 / 弾道で trigger 誤検出のバグ多発。

### `SphereCast` の radius と maxDistance を混同しない
- `radius`: sweep する球の**サイズ**
- `maxDistance`: 球が**移動する距離**
- `hit.distance`: 球の**中心**が移動した距離（接触面までの距離ではない）
- `hit.point`: 接触した相手 collider の表面上の点

---

## async/await 致命罠

> SisterGame は New Input System + async/await を採用しているため、本節は必読。

### Awaitable は **再 await 禁止**
Unity は `Awaitable` インスタンスを**プールしている**。一度 await が完了すると instance は再利用される。同じ instance を 2 回 await すると別の操作の状態を見たり即時完了したり例外を出したりする。**未定義動作**。

```csharp
// NG: 致命罠
Awaitable task = Awaitable.WaitForSecondsAsync(2f);
await task; // 1回目: OK
await task; // 2回目: undefined behavior

// OK: 多重 await が必要なら .AsTask()
var task = Awaitable.WaitForSecondsAsync(2f).AsTask();
await task;
await task; // Task はプールされていないので OK（ただし allocation あり）

// OK: 都度 fresh instance を作る
await Awaitable.WaitForSecondsAsync(2f);
await Awaitable.WaitForSecondsAsync(2f); // 別 instance
```

### `destroyCancellationToken` を必ず渡す
MonoBehaviour プロパティ `destroyCancellationToken` は OnDestroy 開始時に発火する。**全ての Awaitable 待機メソッドに渡す**こと。渡さないと破棄済みオブジェクト上で処理が継続し `MissingReferenceException`。

```csharp
async Awaitable Start()
{
    try
    {
        await Awaitable.WaitForSecondsAsync(5f, destroyCancellationToken);
        transform.position = Vector3.zero; // ここに到達した時点で破棄されていない保証
    }
    catch (OperationCanceledException)
    {
        // 破棄された場合のみ到達。エラーではなく期待動作
    }
}
```

### `BackgroundThreadAsync` 後は Unity API 呼び出し禁止
`Awaitable.BackgroundThreadAsync()` 後、明示的に `MainThreadAsync()` で戻すまで全てが thread pool スレッドで動く。Unity API は thread-safe ではないため、Transform / GameObject / Physics 等の呼び出しは crash or 状態破壊。

```csharp
async Awaitable ProcessData()
{
    await Awaitable.BackgroundThreadAsync();
    var result = HeavyComputation(); // OK: バックグラウンドスレッド

    await Awaitable.MainThreadAsync(); // ★ 明示的に戻す
    transform.position = new Vector3(result, 0, 0); // OK
}
```

### `async void` 禁止、必ず `async Awaitable` 等
`async void` の例外は伝播せずアプリがクラッシュする。`async Awaitable` / `async Awaitable<T>` を使う（Unity の frame loop と統合される）。

### Coroutine の例外は握り潰される
コルーチン内の例外は**サイレントに停止する**（コンソールに stack trace すら出ないことがある）。重要処理は try/catch で囲み `AILogger.Log` で記録する。

---

## パフォーマンス追加規約

### Profiler 操作要点
詳細手順: `@.claude/refs/external/nice-wolf-studio/unity-performance/`

- **Timeline ビュー** = スレッド競合・フレーム時間配分の検出
- **Hierarchy ビュー** = 関数呼び出しコストの特定
- **Deep Profile** = 10〜100 倍のオーバーヘッドあり、頻用しない。代わりに `ProfilerMarker` で特定スコープ計測
- **GC コールスタック有効化** = アロケーション発生箇所の特定

### GC alloc 削減パターン

| 原因 | 対策 |
|---|---|
| `string +` 連結 | `StringBuilder` を field でキャッシュ |
| `LINQ` (Where, Select 等) | 手書き `for` ループ |
| ラムダ capture | `static` ラムダ または field |
| boxing (struct → object) | 型安全 API（`<T>` ジェネリクス）|
| `foreach` over `List<T>` | `for (int i; i < list.Count; i++)` |
| `obj.tag == "..."` | `obj.CompareTag("...")` |
| Physics クエリ | NonAlloc 系（前節）|

### Frame Debugger
draw call / batching 破断 / overdraw を検査する: enable → step-through → shader / pass を検査。

---

## 基礎 API 罠

### `EditorUtility.SetDirty()` 必須（Edit mode の ScriptableObject 変更）
Edit mode でスクリプト経由で SO を変更しても、`EditorUtility.SetDirty()` を呼ばないと**ディスクに保存されない**。

```csharp
settings.value += 10;
#if UNITY_EDITOR
EditorUtility.SetDirty(settings);
#endif
```

### `Instantiate` は 4 引数構文を活用
親 Transform を指定すると world 座標と親設定を一回で済ませられる:

```csharp
// OK: world 座標 + 親設定を一括
Instantiate(prefab, position, rotation, parentTransform);
```

### Transform の non-uniform scaling 禁止
`(2, 4, 2)` のような非均等スケールは **Collider / Light / AudioSource を歪める** + 子オブジェクト rotated 時に skew する + 性能劣化。アセット側でリアルスケールにモデリングし直す。

### Parent-child Transform: 親を `(0,0,0)` に置く
親の位置がずれていると、子オブジェクトの local 座標が想定と一致せずバグの原因。スポーン基準点・コンテナとして使う親オブジェクトは原点配置。

---

## MonoBehaviour 詳細制約

### `FixedUpdate` 内で `Time.deltaTime` を使うべきか
Unity は `FixedUpdate` 内では `Time.deltaTime` を**暗黙的に `Time.fixedDeltaTime` で返す**。動作上は同じだが、**読みやすさのため明示的に `Time.fixedDeltaTime` を使う**ことを推奨。

```csharp
// 動作は同じだが、意図が明確
void FixedUpdate()
{
    rb.AddForce(direction * speed * Time.fixedDeltaTime);
}
```

### ScriptableObject ランタイム制約
プレイモードで SO の値を変更しても、**プレイヤービルドではディスクに永続化できない**（read-only として扱われる）。エディタプレイ時はディスクに反映されるため、デバッグ時の値変更が誤って保存される。プレイ時はランタイム copy を持つ運用にする。

### Coroutine vs Awaitable の選択基準
詳細トレードオフ表は `unity-async-patterns` skill（`.claude/skills/external/nice-wolf-studio/unity-async-patterns/`）を参照。

| 観点 | Coroutine | Awaitable |
|---|---|---|
| 戻り値 | 不可（IEnumerator）| あり（`Awaitable<T>`）|
| 例外 | 握り潰される | propagation 可 |
| メモリ | クラスアロケーション | プール再利用 |
| キャンセル | `StopCoroutine` | `CancellationToken` |
| スレッド | main のみ | `BackgroundThreadAsync` で切替可 |
| 多重 await | 不可（IEnumerator は使い捨て）| **不可（プール）** ★ 注意 |

新規実装は **Awaitable 推奨**（スレッド切替・CancellationToken・例外伝播の利点）。

---

## 関連ドキュメント

- 詳細リファレンス（明示参照時）: `.claude/refs/external/nice-wolf-studio/`
- auto-trigger skill: `.claude/skills/external/nice-wolf-studio/unity-input-correctness/`、`unity-async-patterns/`
- ライセンス帰属: `.claude/rules/_attribution.md`
