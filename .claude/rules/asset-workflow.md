---
description: Asset placeholder, Addressable management, and binding workflow rules
---

# アセットワークフロー規約

## 仮素材（Placeholder）ルール
- アセットが未準備の場合、プレースホルダーで実装を進める
- プレースホルダーGameObjectには `[PLACEHOLDER]` プレフィックスを付ける
  - 例: `[PLACEHOLDER]PlayerCharacter`
- `PlaceholderAsset` コンポーネントを付与して管理情報を記録する
- プレースホルダーのビジュアル:
  - Sprite: マゼンタ色の四角形
  - 3Dモデル: Cubeプリミティブ（マゼンタ色マテリアル）
  - Audio: 無音クリップ
- プレースホルダーもAddressableに登録する（`placeholder` ラベル付与）

## アセット要求リスト
- 新機能実装時、必要アセットを `instruction-formats/asset-request.md` フォーマットで記録
- 各アセットにID、タイプ、説明、フォーマット、優先度、Addressableアドレスを記載

## アセット配置先の命名規則
```
Assets/
├── Sprites/[カテゴリ]/[アセット名].png
├── Models/[カテゴリ]/[アセット名].fbx
├── Animations/[カテゴリ]/[アセット名].anim
├── Audio/
│   ├── BGM/[アセット名].mp3
│   └── SFX/[アセット名].wav
├── Materials/[カテゴリ]/[アセット名].mat
└── Prefabs/[カテゴリ]/[アセット名].prefab
```

## 本番アセット差替え手順
1. アセットを上記ディレクトリ規則に従って配置
2. Addressableに登録（適切なグループ・ラベル・アドレスを設定）
3. `/bind-assets` を実行
4. PlaceholderAssetコンポーネントが自動検出し、Addressable参照に差し替え
5. `[PLACEHOLDER]` プレフィックスを除去
6. PlaceholderAssetコンポーネントを削除
7. `placeholder` ラベルを除去

---

# Addressable アセット管理規約

## 基本方針
- すべてのゲームアセットはAddressableで管理する
- ランタイムのアセット参照は `AssetReference` / `AssetReferenceT<T>` を使用する
- Editor専用の処理（ビルドツール等）のみ `AssetDatabase` の使用を許可する
- 直接参照（Inspector drag & drop）はシーン内の常駐オブジェクト間のみ許可

## グループ設計

### グループ分割基準

| グループ名 | 内容 | パッキング | ロードタイミング |
|------------|------|-----------|----------------|
| `Core` | 起動時に必要なアセット（UI基盤、共通マテリアル） | Pack Together | 起動時プリロード |
| `Player` | プレイヤー関連（スプライト、アニメーション、SE） | Pack Together | タイトル画面で先行ロード |
| `Enemies` | 敵キャラ関連 | Pack Separately | ステージロード時 |
| `Stage_[ID]` | ステージ固有アセット（タイル、背景、BGM） | Pack Together | ステージ選択時 |
| `UI` | UI画面固有のアセット | Pack Separately | 画面遷移時 |
| `Audio_BGM` | BGM（大容量のため分離） | Pack Separately | シーン遷移時 |
| `Audio_SFX` | SE（頻繁にアクセス） | Pack Together | 起動時プリロード |
| `Events` | イベントシーン用アセット | Pack Separately | イベント発火時 |
| `Debug` | デバッグ専用アセット | Pack Together | エディタ/開発ビルドのみ |
| `Placeholder` | 仮素材（本番で除外） | Pack Together | 開発中のみ |

### グループ追加基準
- 新ステージ追加時: `Stage_[ID]` グループを作成
- 単一グループが **50MB** を超えたら分割を検討
- ロードタイミングが異なるアセットは別グループ

## ラベル（タグ）体系

### 用途別ラベル

| ラベル | 用途 | ビルド除外 |
|--------|------|-----------|
| `preload` | 起動時にプリロードするアセット | No |
| `on-demand` | 必要時にロードするアセット | No |
| `placeholder` | 仮素材（本番差替え対象） | **Yes（リリース時）** |
| `debug` | デバッグ専用アセット（ギズモ、テスト用） | **Yes（リリース時）** |
| `dev-only` | 開発ビルド専用（プロファイラ用等） | **Yes（リリース時）** |

### コンテンツ種別ラベル

| ラベル | 対象 |
|--------|------|
| `sprite` | スプライト画像 |
| `animation` | AnimationClip / AnimatorController |
| `audio-bgm` | BGM |
| `audio-sfx` | SE |
| `prefab` | プレハブ |
| `tilemap` | タイルマップ用タイル |
| `material` | マテリアル |
| `timeline` | Timelineアセット |

### ゲームコンテキストラベル

| ラベル | 対象 |
|--------|------|
| `stage-[ID]` | 特定ステージで使用（例: `stage-1-1`） |
| `event-[ID]` | 特定イベントで使用 |
| `boss` | ボス関連アセット |
| `common` | 複数箇所で共用するアセット |

### ラベル付与ルール
- 各アセットに **用途ラベル1つ** + **種別ラベル1つ** + **コンテキストラベル0個以上** を付与
- 例: プレイヤーのidle スプライト → `preload` + `sprite` + `common`
- 例: ステージ1-1のBGM → `on-demand` + `audio-bgm` + `stage-1-1`
- 例: デバッグ用ヒートマップ表示 → `debug` + `material`

## アドレス命名規則

### フォーマット
```
[種別]/[カテゴリ]/[アセット名]
```

### 種別プレフィックス

| プレフィックス | 対象 | 例 |
|---------------|------|-----|
| `sprite` | スプライト | `sprite/player/idle` |
| `anim` | アニメーション | `anim/player/run` |
| `sfx` | SE | `sfx/attack/slash` |
| `bgm` | BGM | `bgm/stage/forest` |
| `prefab` | プレハブ | `prefab/enemy/slime` |
| `tile` | タイル | `tile/terrain/grass` |
| `mat` | マテリアル | `mat/effect/glow` |
| `ui` | UI用アセット | `ui/hud/healthbar` |
| `timeline` | Timeline | `timeline/event/opening` |

### 命名ルール
- すべて小文字、区切りは `/`（Addressableのパスセパレータ）
- 単語間の区切りはハイフン `-`（例: `sprite/player/idle-left`）
- ファイルパスではなく論理的な名前を使用する
- NG: `Assets/Sprites/Player/idle.png` → OK: `sprite/player/idle`

## ランタイムロード規約

### AssetReference の使用
```csharp
// SerializeFieldでInspectorから設定
[SerializeField] private AssetReferenceSprite _playerSprite;
[SerializeField] private AssetReferenceGameObject _enemyPrefab;

// ロード（awaitパターン）
Sprite sprite = await _playerSprite.LoadAssetAsync<Sprite>().Task;

// 解放（不要になったら必ず呼ぶ）
_playerSprite.ReleaseAsset();
```

### アドレス文字列での動的ロード
```csharp
// ステージ固有アセットなど、動的に決まる場合のみ使用
AsyncOperationHandle<Sprite> handle = Addressables.LoadAssetAsync<Sprite>("sprite/enemy/slime");
Sprite result = await handle.Task;

// 解放
Addressables.Release(handle);
```

### ラベルによる一括ロード
```csharp
// ステージ切替時にステージアセットを一括プリロード
AsyncOperationHandle<IList<Sprite>> handle =
    Addressables.LoadAssetsAsync<Sprite>("stage-1-1", null);
IList<Sprite> sprites = await handle.Task;

// ステージ終了時に一括解放
Addressables.Release(handle);
```

### ロード・解放の原則
- **ロードしたアセットは必ず解放する**（参照カウント管理）
- `OnDestroy()` または `OnDisable()` で解放処理を入れる
- シーン遷移時は `Addressables.Release()` で明示解放
- `Addressables.InstantiateAsync()` で生成した場合は `Addressables.ReleaseInstance()` で破棄

## ビルド除外ルール

### リリースビルド時に除外するラベル
- `placeholder` — 仮素材はリリースに含めない
- `debug` — デバッグ専用アセットはリリースに含めない
- `dev-only` — 開発ビルド専用アセット

### 除外方法
- Addressable グループ設定の `Include in Build` を条件コンパイルで制御
- またはビルドスクリプトで `Debug` / `Placeholder` グループを除外
```csharp
#if !UNITY_EDITOR && !DEVELOPMENT_BUILD
// Debug, Placeholder グループをビルドから除外
#endif
```

### デバッグアセットのガード
```csharp
// ランタイムでデバッグアセットを参照するコードには条件コンパイルを付ける
#if UNITY_EDITOR || DEVELOPMENT_BUILD
    AsyncOperationHandle<GameObject> debugHandle =
        Addressables.LoadAssetAsync<GameObject>("prefab/debug/heatmap-overlay");
#endif
```

## Editor専用コード（AssetDatabase使用許可範囲）

以下のEditor専用ツールでは `AssetDatabase` の使用を継続する:
- `StageBuilder.cs` — ステージシーン構築（Editorメニュー操作）
- `EventSceneBuilder.cs` — イベントシーン構築
- `TemplateManager.cs` — テンプレートプレハブ参照
- `AnimatorBuilder.cs` — AnimatorController生成
- `SceneDescriptor.cs` — シーン解析

ランタイムコードでの `AssetDatabase` 使用は禁止。

## Addressable 導入チェックリスト（新規プロジェクト設定時）

1. [ ] Package Manager から `com.unity.addressables` をインストール
2. [ ] `AddressableAssetSettings` を作成（Window > Asset Management > Addressables > Groups）
3. [ ] 上記グループ設計に従ってグループを作成
4. [ ] `Placeholder` グループを作成し、仮素材を登録
5. [ ] `Debug` グループを作成し、リリース除外設定を適用
6. [ ] プロファイル設定（Local / Remote パス）
7. [ ] ビルドスクリプトにラベル除外ロジックを追加
8. [ ] `.asmdef` に `Unity.Addressables` と `Unity.ResourceManager` を追加

---

# シーン遷移と Asset Lifecycle

> Sources: nice-wolf-studio/unity-claude-skills (MIT) — unity-scene-assets

## シーンアーキテクチャ戦略の選択

| 戦略 | 用途 | 特徴 |
|---|---|---|
| **Single scene** | プロトタイプ・ゲームジャム | 最速。複雑性ゼロ。すぐ限界が来る |
| **Scene-per-level** | 線形進行（プラットフォーマー、パズル）| `LoadScene(name, Single)` で切替。`DontDestroyOnLoad` なしには共有状態を持てない |
| **Additive scene composition** | オープンワールド・常駐 HUD・共有システム | 「Boot」or「Persistent」シーンが常駐、gameplay/UI シーンを additive ロード。最も柔軟、最も複雑 |

SisterGame は 2D サイドスクローラなので **Scene-per-level** または **Additive composition** が候補。`/design-stage` で設計時に判定する。

## SceneCoordinator パターン（Additive 構成）

ゲーム全体の永続状態（GameManager 等）を Persistent シーンに置き、各ステージシーンを additive にロード/アンロードする:

```csharp
public class SceneCoordinator : MonoBehaviour
{
    [SerializeField] private string persistentSceneName = "Persistent";
    private string _currentContentScene;

    public static SceneCoordinator Instance { get; private set; }

    void Awake()
    {
        if (Instance != null) { Destroy(gameObject); return; }
        Instance = this;
        DontDestroyOnLoad(gameObject);
    }

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
    static void ResetStatic() => Instance = null;

    public async Awaitable LoadContentScene(string sceneName)
    {
        if (!string.IsNullOrEmpty(_currentContentScene))
            await SceneManager.UnloadSceneAsync(_currentContentScene);

        await SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Additive);
        _currentContentScene = sceneName;

        // ★ 重要: SetActiveScene を忘れると新規スポーンが Persistent 側に行ってしまう
        SceneManager.SetActiveScene(SceneManager.GetSceneByName(sceneName));
    }
}
```

**罠**: `SceneManager.SetActiveScene` を忘れると、`Instantiate` した新規オブジェクトが Persistent シーンに置かれ、誤った lightmap / navmesh / unload 挙動になる。Additive ロード後は必ず呼ぶ。

## ローディング画面と AsyncOperation

### `AsyncOperation.progress` は **0.9 で止まる罠**

`allowSceneActivation = false` の状態では `progress` は最大 **0.9** までしか上がらない。100% 表示にしたいなら正規化が必要:

```csharp
var loadOp = SceneManager.LoadSceneAsync(sceneName, LoadSceneMode.Additive);
loadOp.allowSceneActivation = false;

while (loadOp.progress < 0.9f)
{
    // 0-1 に正規化（0.9 を 1.0 として扱う）
    float normalizedProgress = Mathf.Clamp01(loadOp.progress / 0.9f);
    onProgress?.Invoke(normalizedProgress);
    await Awaitable.NextFrameAsync(destroyCancellationToken);
}

// アクティベート（即座にシーン切替）
loadOp.allowSceneActivation = true;
while (!loadOp.isDone)
    await Awaitable.NextFrameAsync(destroyCancellationToken);
```

### 最低表示時間の保証
ローディング画面のフラッシュ防止には `Time.realtimeSinceStartup` を使う（`Time.time` は `timeScale` 影響を受ける）:

```csharp
float startTime = Time.realtimeSinceStartup;
// ... ロード処理 ...
float elapsed = Time.realtimeSinceStartup - startTime;
if (elapsed < minimumLoadScreenTime)
    await Awaitable.WaitForSecondsAsync(minimumLoadScreenTime - elapsed, destroyCancellationToken);
```

## Addressables ハンドル解放の罠

### Instance がまだ生きているうちに Release しない
ハンドル `Release` 時に instantiated オブジェクトがまだ参照していると、ピンク マテリアル（best case）or クラッシュ（worst case）になる。

```csharp
// NG: GameObject 破棄前に Release
Addressables.Release(handle);
Destroy(spawnedEnemy); // 既にマテリアルがピンク

// OK: GameObject 破棄を完了してから
Destroy(spawnedEnemy);
await Awaitable.NextFrameAsync(); // Destroy 完了待ち
Addressables.Release(handle);

// または InstantiateAsync を使えば自動追跡される
var instance = await Addressables.InstantiateAsync(key).Task;
// ... 使用 ...
Addressables.ReleaseInstance(instance); // ハンドルも自動解放
```

## 詳細リファレンス

シーン遷移 / 資産プリロード / Resources → Addressables 移行チェックリストの完全版は:
`@.claude/refs/external/nice-wolf-studio/unity-scene-assets/SKILL.md`
