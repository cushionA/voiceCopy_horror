# UniCli Command Reference

Complete list of built-in commands. Run `unicli commands` to see all commands including auto-generated Settings commands.

## Core

### Compile
Compile scripts and return results.
```bash
unicli exec Compile
unicli exec Compile --json
```

### CompilePlayer
Compile player scripts for a specific build target.
```bash
unicli exec CompilePlayer
unicli exec CompilePlayer --target Android
unicli exec CompilePlayer --target iOS --extraScriptingDefines MY_DEFINE
```
Parameters: `--target <BuildTarget>`, `--extraScriptingDefines <defines>`

## Console

### Console.GetLog
Get console log entries.
```bash
unicli exec Console.GetLog
```

### Console.Clear
Clear the console.
```bash
unicli exec Console.Clear
```

## PlayMode

### PlayMode.Enter
Enter play mode.
```bash
unicli exec PlayMode.Enter
```

### PlayMode.Exit
Exit play mode.
```bash
unicli exec PlayMode.Exit
```

### PlayMode.Pause
Toggle pause state.
```bash
unicli exec PlayMode.Pause
```

## Menu

### Menu.List
List all available menu items.
```bash
unicli exec Menu.List
```

### Menu.Execute
Execute a Unity menu item by path.
```bash
unicli exec Menu.Execute --menuPath "Window/General/Console"
unicli exec Menu.Execute --menuPath "File/Save Project"
unicli exec Menu.Execute --menuPath "Assets/Refresh"
```
Parameters: `--menuPath <string>` (required)

Note: `File/Quit` is blocked for safety in some CLI implementations.

## TestRunner

### TestRunner.RunEditMode
Run EditMode tests.
```bash
unicli exec TestRunner.RunEditMode
unicli exec TestRunner.RunEditMode --testNameFilter MyTest
```
Parameters: `--testNameFilter <pattern>`

### TestRunner.RunPlayMode
Run PlayMode tests.
```bash
unicli exec TestRunner.RunPlayMode
unicli exec TestRunner.RunPlayMode --testNameFilter "MyNamespace.MyTest"
```
Parameters: `--testNameFilter <pattern>`

## GameObject

### GameObject.Find
Find GameObjects in the scene.
```bash
unicli exec GameObject.Find --name "Main Camera"
unicli exec GameObject.Find --tag Player
unicli exec GameObject.Find --tag Player --includeInactive
```
Parameters: `--name <string>`, `--tag <string>`, `--includeInactive` (flag)

### GameObject.GetComponents
Get components attached to a GameObject.
```bash
unicli exec GameObject.GetComponents --instanceId 1234
```
Parameters: `--instanceId <int>` (required)

### GameObject.SetActive
Set a GameObject's active state.
```bash
unicli exec GameObject.SetActive --instanceId 1234 --active true
```
Parameters: `--instanceId <int>`, `--active <bool>`

### GameObject.GetHierarchy
Get the full scene hierarchy.
```bash
unicli exec GameObject.GetHierarchy
```

### GameObject.AddComponent
Add a component to a GameObject.
```bash
unicli exec GameObject.AddComponent --path "Player" --typeName BoxCollider
```
Parameters: `--path <string>` or `--instanceId <int>`, `--typeName <string>` (required)

### GameObject.RemoveComponent
Remove a component from a GameObject.
```bash
unicli exec GameObject.RemoveComponent --componentInstanceId 1234
```
Parameters: `--componentInstanceId <int>` (required)

## Prefab

### Prefab.GetStatus
Get the prefab status of a GameObject.
```bash
unicli exec Prefab.GetStatus --path "MyPrefabInstance"
```

### Prefab.Instantiate
Instantiate a prefab into the scene.
```bash
unicli exec Prefab.Instantiate --assetPath "Assets/Prefabs/Enemy.prefab"
```
Parameters: `--assetPath <string>` (required)

### Prefab.Save
Save a GameObject as a prefab asset.
```bash
unicli exec Prefab.Save --path "Player" --assetPath "Assets/Prefabs/Player.prefab"
```
Parameters: `--path <string>`, `--assetPath <string>` (required)

### Prefab.Apply
Apply prefab overrides.
```bash
unicli exec Prefab.Apply --path "MyPrefabInstance"
```

### Prefab.Unpack
Unpack a prefab instance.
```bash
unicli exec Prefab.Unpack --path "MyPrefabInstance"
unicli exec Prefab.Unpack --path "MyPrefabInstance" --completely
```
Parameters: `--path <string>`, `--completely` (flag)

## AssetDatabase

### AssetDatabase.Find
Search for assets.
```bash
unicli exec AssetDatabase.Find --filter "t:Texture2D"
unicli exec AssetDatabase.Find --filter "Player t:Prefab"
```
Parameters: `--filter <string>` (required)

### AssetDatabase.Import
Import/reimport an asset.
```bash
unicli exec AssetDatabase.Import --path "Assets/Textures/icon.png"
```

### AssetDatabase.GetPath
Get asset path by GUID.
```bash
unicli exec AssetDatabase.GetPath --guid "abc123..."
```

### AssetDatabase.Delete
Delete an asset.
```bash
unicli exec AssetDatabase.Delete --path "Assets/Prefabs/Old.prefab"
```

## Project

### Project.Inspect
Get project information (Unity version, paths, etc).
```bash
unicli exec Project.Inspect
```

## PackageManager

### PackageManager.List
List installed packages.
```bash
unicli exec PackageManager.List
```

### PackageManager.Add
Add a package.
```bash
unicli exec PackageManager.Add --packageIdOrName com.unity.mathematics
```

### PackageManager.Remove
Remove a package.
```bash
unicli exec PackageManager.Remove --packageIdOrName com.unity.mathematics
```

### PackageManager.Search
Search the package registry.
```bash
unicli exec PackageManager.Search --query "input"
```

## AssemblyDefinition

### AssemblyDefinition.List
List all assembly definitions in the project.
```bash
unicli exec AssemblyDefinition.List
```

### AssemblyDefinition.Get
Get details of an assembly definition.
```bash
unicli exec AssemblyDefinition.Get --name "MyGame.Core"
```

### AssemblyDefinition.Create
Create a new assembly definition.
```bash
unicli exec AssemblyDefinition.Create --path "Assets/Scripts/Core" --name "MyGame.Core"
```

### AssemblyDefinition.AddReference
Add a reference to an assembly definition.
```bash
unicli exec AssemblyDefinition.AddReference --name "MyGame.Core" --reference "MyGame.Utils"
```

### AssemblyDefinition.RemoveReference
Remove a reference from an assembly definition.
```bash
unicli exec AssemblyDefinition.RemoveReference --name "MyGame.Core" --reference "MyGame.Utils"
```

## Scene

### Scene.List
List all loaded scenes.
```bash
unicli exec Scene.List
```

### Scene.GetActive
Get the active scene.
```bash
unicli exec Scene.GetActive
```

### Scene.SetActive
Set the active scene.
```bash
unicli exec Scene.SetActive --name "Level1"
```

### Scene.Open
Open a scene by asset path.
```bash
unicli exec Scene.Open --path "Assets/Scenes/Level1.unity"
unicli exec Scene.Open --path "Assets/Scenes/Additive.unity" --additive
```
Parameters: `--path <string>` (required), `--additive` (flag)

### Scene.Close
Close a loaded scene.
```bash
unicli exec Scene.Close --name "Additive"
```

### Scene.Save
Save scenes.
```bash
unicli exec Scene.Save --all
unicli exec Scene.Save --name "Level1"
unicli exec Scene.Save --name "Level1" --saveAsPath "Assets/Scenes/Level1_backup.unity"
```
Parameters: `--all` (flag), `--name <string>`, `--saveAsPath <string>`

### Scene.New
Create a new scene.
```bash
unicli exec Scene.New
unicli exec Scene.New --empty --additive
```
Parameters: `--empty` (flag), `--additive` (flag)

## Utility

### TypeCache.List
List types derived from a base type.
```bash
unicli exec TypeCache.List --baseType "UnityEngine.MonoBehaviour"
```

### TypeInspect
Inspect nested types of a given type.
```bash
unicli exec TypeInspect --typeName "UnityEditor.PlayerSettings"
```

## Top-Level CLI Subcommands

These are `unicli` subcommands (not `exec` commands):

| Subcommand | Description |
|---|---|
| `unicli check` | Verify package installation and editor connection |
| `unicli install` | Install UniCli package into Unity project |
| `unicli commands` | List all available commands (including auto-generated) |
| `unicli status` | Show connection status and project info |
| `unicli completions <shell>` | Generate shell completions (bash/zsh/fish) |

Add `--json` to `check`, `commands`, or `status` for JSON output.
