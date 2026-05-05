---
name: unicli
description: Use this skill when the user wants to interact with Unity Editor from the terminal using UniCli, or when working on Unity projects and needing to compile, test, inspect GameObjects, manage scenes/prefabs/packages, or execute editor commands via CLI. Trigger whenever the user mentions "unicli", "Unity CLI", "Unity command line", or wants to perform Unity Editor operations like compiling scripts, running tests, finding GameObjects, managing scenes, checking prefab status, or controlling play mode from the terminal. Also trigger when the user is using Claude Code with Unity and needs to run editor commands, or when discussing AI-agent integration with Unity Editor. This skill covers all UniCli commands, custom command authoring, and troubleshooting.
---

# UniCli Skill

UniCli is a CLI tool that controls Unity Editor via Named Pipe (local IPC). No MCP server, no Python, no network — just a single NativeAOT binary talking directly to a Unity Editor plugin.

## Architecture

```
unicli (CLI binary) ← Named Pipe (length-prefixed JSON) → Unity Editor (com.yucchiy.unicli-server)
```

- Pipe name is derived from SHA256 of the project's Assets path (each project gets its own connection)
- Requires Unity 2022.3+, macOS (arm64/x64) or Windows (x64)

## Setup

```bash
# 1. Install CLI — download binary from GitHub releases and add to PATH
# https://github.com/yucchiy/UniCli/releases

# 2. Install Unity package (from terminal, in project directory)
unicli install

# Or manually via Package Manager git URL:
# https://github.com/yucchiy/UniCli.git?path=src/UniCli.Unity/Packages/com.yucchiy.unicli-server

# 3. Verify connection
unicli check
unicli status
```

## Command Structure

All commands follow: `unicli exec <Command> [--param value] [--json]`

Global options for `exec`:
- `--json` — machine-readable JSON output
- `--timeout <ms>` — command timeout in milliseconds
- `--no-focus` — don't bring Unity to front
- `--help` — show command parameters

Parameter passing:
```bash
# Key-value (recommended)
unicli exec GameObject.Find --name "Main Camera"

# Boolean flags (no value needed)
unicli exec GameObject.Find --includeInactive

# Raw JSON
unicli exec GameObject.Find '{"name":"Main Camera"}'
```

## Command Quick Reference

For the full command list with parameters and examples, read `references/commands.md`.

### Most-Used Commands

| Task | Command |
|---|---|
| Compile | `unicli exec Compile` |
| Compile for platform | `unicli exec CompilePlayer --target Android` |
| Run edit-mode tests | `unicli exec TestRunner.RunEditMode` |
| Run play-mode tests | `unicli exec TestRunner.RunPlayMode` |
| Find GameObject | `unicli exec GameObject.Find --name "Player"` |
| Get hierarchy | `unicli exec GameObject.GetHierarchy` |
| Open scene | `unicli exec Scene.Open --path "Assets/Scenes/Main.unity"` |
| Enter play mode | `unicli exec PlayMode.Enter` |
| Check console | `unicli exec Console.GetLog` |
| List packages | `unicli exec PackageManager.List` |
| Eval arbitrary C# | `unicli exec Eval --code "Debug.Log(42);"` |

## Custom Commands

Users can extend UniCli by writing C# handlers in their Unity project. Auto-discovered, no registration needed.

```csharp
// Inherit CommandHandler<TRequest, TResponse>
public sealed class MyHandler : CommandHandler<MyRequest, MyResponse>
{
    public override string CommandName => "MyApp.DoThing";
    public override string Description => "Does the thing";

    protected override ValueTask<MyResponse> ExecuteAsync(MyRequest request)
    {
        // Unity Editor API calls here
        return new ValueTask<MyResponse>(new MyResponse { result = "done" });
    }
}

[Serializable]
public class MyRequest { public string input; }

[Serializable]
public class MyResponse { public string result; }
```

Then: `unicli exec MyApp.DoThing --input "hello"`

Use `Unit` as type parameter for no-input or no-output commands.

## Settings Commands (Auto-Generated)

UniCli auto-generates commands for `PlayerSettings`, `EditorSettings`, `EditorUserBuildSettings` via Roslyn Source Generator. Pattern:

- `<Settings>.Inspect` — get all values
- `<Settings>.Set<Property>` — set a property
- `<Settings>.<Nested>.Set<Property>` — set nested property
- `<Settings>.<Method>` — call Set/Get method

```bash
unicli exec PlayerSettings.Inspect
unicli exec PlayerSettings.SetCompanyName --value "MyCompany"
unicli exec PlayerSettings.Android.SetMinSdkVersion --value AndroidApiLevel28
unicli exec PlayerSettings.SetScriptingBackend --buildTarget Android --value IL2CPP
```

Enum values are passed as strings. Invalid values return an error with valid options listed.

## Claude Code Integration

```bash
# Install plugin
/plugin marketplace add yucchiy/UniCli
/plugin install unicli@unicli
```

This gives Claude Code the ability to compile, test, inspect, and manage Unity projects as part of its coding workflow.

## PlayMode対応（サーバー自動再起動）

UniCliサーバーは `playModeStateChanged` イベントでドメインリロード後に自動再起動する。
PlayMode遷移時に2-4秒の接続不可期間があるが、CLI側がリトライすれば自動復帰する。

| 操作 | コマンド | 備考 |
|---|---|---|
| PlayMode開始 | `unicli exec PlayMode.Enter` | 遷移後数秒でサーバー復帰 |
| PlayMode停止 | `unicli exec PlayMode.Exit` | |
| PlayMode中のステータス | `unicli exec PlayMode.Status` | |
| PlayMode中のコンソール | `unicli exec Console.GetLog` | |
| PlayMode中のポーズ | `unicli exec PlayMode.Pause` | |

### 制限事項

| 項目 | 詳細 |
|---|---|
| **PlayModeテスト** | `TestRunner.RunPlayMode` はCLI側が長時間接続を維持できないため非推奨。**PlayModeテストはユーザーがUnity Test Runnerから手動実行する。** |
| **リトライ必要** | PlayMode遷移直後はサーバー再起動中のため、接続失敗する場合がある。`tools/unicli-retry.sh` ラッパーまたは手動リトライで対応。 |

## Troubleshooting

| Problem | Solution |
|---|---|
| Connection refused | Ensure Unity Editor is open with the project. Run `unicli check` |
| Command timeout | Unity may be busy (compiling, etc). Increase `--timeout` |
| Command not found | Run `unicli commands` to list available commands |
| Unity throttles in background | Edit → Preferences → General → Interaction Mode → "No Throttling" |
| Package not installed | Run `unicli install` in the project directory |
| Server not responding after PlayMode | ドメインリロード中。2-4秒待ってリトライ |
