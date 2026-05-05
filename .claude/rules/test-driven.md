---
description: Test-driven development workflow rules for Unity game features
---

# TDD開発規約

## ワークフロー
1. テストファイルを先に作成する（Red）
2. テストが全てFailすることを確認する
3. 実装コードを作成する
4. テストが全てPassすることを確認する（Green）
5. `python tools/feature-db.py` で feature-log.db に完了記録を追加する

## テスト命名規則
- フォーマット: `[機能名]_[条件]_[期待結果]`
- 例: `PlayerMovement_WhenSpeedIsZero_ShouldNotMove`
- 例: `HealthSystem_WhenDamageTaken_ShouldReduceHealth`

## テストファイル配置
- Edit Mode: `Tests/EditMode/[機能名]Tests.cs`
- Play Mode: `Tests/PlayMode/[機能名]PlayTests.cs`

## Edit Mode vs Play Mode
- Edit Mode: ロジック単体テスト、データ変換、計算処理
- Play Mode: MonoBehaviour連携、物理演算、コルーチン、シーン動作

## 結合テスト（Cross-System Testing）

単体テストに加え、以下の観点で結合テストを作成する。
配置先: `Tests/EditMode/Integration_{テスト名}Tests.cs`

### 必須観点

1. **既存ロジック呼び出し検証**: 新コードが既存ユーティリティを正しく経由しているか
   - 例: ProjectileHitProcessorがHpArmorLogic.ApplyDamageを経由し、HPクランプ・アーマー処理が適用されるか
   - **NG**: 「HPが減った」だけの検証 → **OK**: 「HP >= 0 にクランプされる」「アーマーブレイクボーナスが乗る」

2. **状態シーケンス検証**: 同じ操作を複数回行った時に状態が壊れないか
   - 例: ActionExecutorでA→B→Aと実行した後、OnCompletedが1回だけ発火するか
   - 例: HudのTweenBarを連続呼び出しした時に前回のハンドルが正しくキャンセルされるか

3. **境界値・不変条件検証**: 単体テストの「正常系OK」だけでなく「壊れない保証」を追加
   - HP < 0 にならない、インデックスが範囲外にならない、リソースがリークしない
   - イベント購読数が増え続けない（subscribe/unsubscribeの対称性）

### テスト設計チェックリスト（機能実装時に確認）

- [ ] この機能は他システムのメソッドを呼んでいるか？ → 呼び先の効果まで検証するテストを書く
- [ ] この機能はイベントを購読/発行しているか？ → 購読解除・多重購読のテストを書く
- [ ] この機能は状態を持つか？ → 連続操作・リセット後の再操作テストを書く
- [ ] この機能はリソース（ハンドル・マテリアル等）を確保するか？ → 解放テストを書く

## feature-log.db 記録方法 (SQLite)
```bash
# 機能追加
python tools/feature-db.py add "機能名" --tests テストファイル1 テストファイル2 --impl 実装ファイル1

# ステータス更新
python tools/feature-db.py update "機能名" --status complete --test-passed 3 --test-failed 0

# 機能取得
python tools/feature-db.py get "機能名"

# 一覧表示
python tools/feature-db.py list [--status in_progress|complete|failed]

# サマリー
python tools/feature-db.py summary
```

## テスト実行
- Edit Mode: Unity CLI `-runTests -testPlatform EditMode`
- Play Mode: Unity CLI `-runTests -testPlatform PlayMode`
- MCP経由: unity-mcp の run_tests ツール使用

---

# Unity Test Framework (UTF) API リファレンス

> Sources: nice-wolf-studio/unity-claude-skills (MIT) — unity-testing
>
> 本セクションは「**Unity でどう実装するか**」の技術観点。「何をテストすべきか」のビジネス観点は本ファイル上部の結合テスト 3 観点を参照。

## NUnit / Unity 固有属性

### 標準 NUnit 属性

| 属性 | 用途 |
|---|---|
| `[Test]` | 同期テスト |
| `[TestFixture]` | テストクラスのマーカー（任意、ない場合も認識される）|
| `[SetUp]` / `[TearDown]` | 各テストの前後に実行 |
| `[OneTimeSetUp]` / `[OneTimeTearDown]` | クラス全体で 1 回実行 |
| `[TestCase(args...)]` | パラメタ化テスト |
| `[Category("Unit")]` | カテゴリ分類（CLI で `-testCategory` で絞込）|

### Unity 固有属性

| 属性 | 用途 |
|---|---|
| `[UnityTest]` | Coroutine ベースのテスト（yield 命令対応）|
| `[UnitySetUp]` / `[UnityTearDown]` | yield 対応の Setup/Teardown |
| `[RequiresPlayMode(true/false)]` | Play Mode / Edit Mode を強制 |
| `[UnityPlatform]` | 特定プラットフォームに限定 |
| `[TestMustExpectAllLogs]` | 全 log がエクスペクト済みであることを要求 |
| `[ConditionalIgnore]` | 条件付きでテストをスキップ |
| `[PrebuildSetup]` / `[PostBuildCleanup]` | プレイヤービルド前後に実行 |

## Yield 命令 (Play Mode `[UnityTest]` 内)

| Yield | 効果 |
|---|---|
| `yield return null` | 1 フレームスキップ |
| `yield return new WaitForSeconds(t)` | スケール時間で `t` 秒待機 |
| `yield return new WaitForSecondsRealtime(t)` | 実時間で `t` 秒待機 |
| `yield return new WaitForFixedUpdate()` | 次の物理更新まで待機 |
| `yield return new WaitForEndOfFrame()` | フレーム終端まで（**バッチモードで動かない**ことに注意）|
| `yield return new WaitUntil(() => cond)` | 条件 true まで待機 |
| `yield return new WaitWhile(() => cond)` | 条件 true の間待機 |

## MonoBehaviour テストの基本骨格

```csharp
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using System.Collections;

public class PlayerControllerTests
{
    private GameObject _playerObject;
    private PlayerController _player;

    [UnitySetUp]
    public IEnumerator SetUp()
    {
        _playerObject = new GameObject("Player");
        _player = _playerObject.AddComponent<PlayerController>();
        yield return null; // Awake/Start 待ち
    }

    [UnityTearDown]
    public IEnumerator TearDown()
    {
        Object.Destroy(_playerObject);
        yield return null; // Destroy 完了待ち（テスト間汚染防止）
    }

    [UnityTest]
    public IEnumerator Player_MovesForward_WhenInputApplied()
    {
        var startPos = _player.transform.position;
        _player.Move(Vector3.forward);

        yield return new WaitForFixedUpdate();

        Assert.Greater(_player.transform.position.z, startPos.z);
    }
}
```

**重要**: `[UnityTearDown]` で `Object.Destroy` を必ず呼ぶ。`yield return null` で破棄完了を待つ。これを怠るとテスト間汚染で **flaky test** の温床になる。

## LogAssert（ログ検証）

`Debug.LogError` と `Debug.LogException` は**自動的にテスト失敗扱い**になる。エクスペクトする場合は `LogAssert.Expect` を使う:

```csharp
[Test]
public void DamageNegative_ThrowsAndLogsError()
{
    LogAssert.Expect(LogType.Error, "Damage cannot be negative");
    Assert.Throws<ArgumentException>(() => weapon.TakeDamage(-1));
}
```

`LogAssert.NoUnexpectedReceived()` で「予期しないログがないこと」を断言できる。

## パラメタ化テスト

```csharp
[TestCase(100, 30, 70)]
[TestCase(100, 100, 0)]
[TestCase(100, 150, 0)]   // 境界値: HP < 0 にならない
[TestCase(50, 10, 40)]
public void TakeDamage_CalculatesCorrectly(int maxHp, int damage, int expectedHp)
{
    var health = new HealthSystem(maxHp);
    health.TakeDamage(damage);
    Assert.AreEqual(expectedHp, health.CurrentHealth);
}
```

## 例外テスト

```csharp
[Test]
public void Inventory_AddNull_ThrowsException()
{
    var inventory = new Inventory(maxSlots: 10);
    Assert.Throws<ArgumentNullException>(() => inventory.Add(null));
}
```

## Fake / Stub による依存注入

```csharp
public class FakeAudioService : IAudioService
{
    public bool PlaySoundCalled { get; private set; }
    public void PlaySound(string name) => PlaySoundCalled = true;
}

[Test]
public void Attack_PlaysSound()
{
    var fakeAudio = new FakeAudioService();
    var weapon = new Weapon(fakeAudio);
    weapon.Attack();
    Assert.IsTrue(fakeAudio.PlaySoundCalled);
}
```

## CLI 引数（CI/CD）

```bash
# Edit Mode
Unity -runTests -batchmode -projectPath /path \
  -testPlatform EditMode -testResults /path/results.xml

# カテゴリ絞込
Unity -runTests -batchmode -projectPath /path \
  -testFilter "HealthSystemTests" -testCategory "Unit;Integration" \
  -testResults /path/results.xml
```

| 引数 | 説明 |
|---|---|
| `-runTests` | 必須フラグ |
| `-testPlatform` | `EditMode` / `PlayMode` / `BuildTarget` |
| `-testFilter` | 「;」区切り or regex（`!` 接頭辞で否定）|
| `-testCategory` | 「;」区切り（`!` 接頭辞で否定）|

> **注意**: `-runTests` と `-quit` は併用禁止（メモリ `feedback_unity-cli-batch-test.md` 参照）

## Unity Test Framework Anti-patterns

### ❌ 同期テストで `[UnityTest]` を使う
`[UnityTest]` は yield instruction が必要なときだけ使う。同期で済むなら `[Test]` を使うこと（実行が高速）。

### ❌ `[UnityTearDown]` で GameObject を破棄しない
テスト間汚染で flaky test の原因。必ず破棄 + `yield return null` で完了待ち。

### ❌ private メソッドを直接テスト
public API 経由で動作を確認する。private は実装詳細。

### ❌ `WaitForSeconds` でハードコード待機
タイミング依存で flaky になりがち。`WaitUntil(() => condition)` で条件待ちに変える。

### ❌ テスト実行順依存
`[Test]` の順序は不定。`[OneTimeSetUp]` / `SetUp` で都度初期化。

### ❌ ログエラーを無視
`Debug.LogError` は自動失敗扱い。期待されるならば `LogAssert.Expect` を明示。

### ❌ プロダクションコードと同じ asmdef にテスト配置
テスト用 asmdef を分離（`Tests/EditMode/*.asmdef`、`Tests/PlayMode/*.asmdef`）。

## 詳細リファレンス

完全版は `@.claude/refs/external/nice-wolf-studio/unity-testing/SKILL.md` を参照。
