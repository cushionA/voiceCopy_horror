# UHFPS 機能インベントリ

> **目的**: voice_horror のゲームメカニクスを実装する際、UHFPS の既存機能を最大限活用するためのマップ。
> **配置**: `voice_Horror_Game/Assets/ThunderWire Studio/UHFPS/`（約 2.3 GB、git ignore 済）
> **記録日**: 2026-05-05
> **記録対象**: UHFPS Runtime Scripts のみ（Editor / Scriptables 除く）

---

## 1. voice_horror コアメカニクス × UHFPS 対応マップ

| voice_horror 機能 | UHFPS 流用元 | 自前実装の必要性 | 優先度 |
|---|---|---|---|
| 一人称 FPS 移動 | `Controllers/Player/PlayerStateMachine.cs` + FSM | 🟢 そのまま使用 | - |
| 足音 | `Controllers/Player/FootstepsSystem.cs` | 🟢 そのまま使用 | - |
| プレイヤーHP | `Controllers/Player/PlayerHealth.cs` | 🟡 ホラー仕様に拡張 | 中 |
| 文書 12 個収集 | `Core/Inventory/` (Item/Behaviour/Slot) | 🟡 文書 UI ＋ 完読フラグ管理を追加 | 高 |
| 文書を読む UI | `UI/` + `Core/Inventory/Behaviour` | 🟡 ページめくり機構を追加 | 高 |
| 幽霊 AI 3 体 | `Core/AI/NPCStateMachine.cs` + AIStates + Waypoints | 🔴 性格別 BT/FSM、視野・聴覚、ボイス強化応答 | 高 |
| 少女の電話演出 | `Core/Dialogue/DialogueSystem.cs` | 🔴 TTS 動的呼び出し、声混じり演出 | 高 |
| ボイス録音 | （なし） | 🔴 Microphone API、保存、永続化 | 高 |
| ボイス類似度判定 | （なし） | 🔴 MFCC 抽出、cosine similarity | 高 |
| ボイス強化システム | （なし、AI 側に統合） | 🔴 マイク入力検出 → AI パラメータ強化 | 高 |
| 推理パズル（死因照合） | `Core/Puzzle/` | 🟡 voice_horror 固有 UI を追加 | 中 |
| Jumpscare | `Core/Game/Jumpscare/` | 🟢 そのまま使用、演出カスタムのみ | 低 |
| 隠れる（クローゼット等） | `Interact/Hiding/` | 🟢 そのまま使用 | - |
| 懐中電灯 | `Interact/Lights/` | 🟢 そのまま使用 | - |
| セーブ/ロード | `Core/SaveGame/` (Manager/Reader/Encryptor) | 🟡 録音データの暗号化保存追加 | 中 |
| エンディング分岐 | （なし、自前） | 🔴 類似度→分岐ロジック | 高 |
| 主目標表示 (HUD) | `Core/Objectives/` | 🟢 そのまま使用 | - |
| メインメニュー | `Core/Game/MainMenuManager.cs` + `UI/Menu/` | 🟡 デザイン差替えのみ | 低 |

---

## 2. UHFPS Runtime ディレクトリ構造（カテゴリ別）

### 2.1 Controllers — プレイヤー操作系
| パス | 主要クラス | 用途 |
|---|---|---|
| `Controllers/Camera/` | （複数） | 一人称カメラ・揺れ・FOV |
| `Controllers/Items/` | （複数） | 装備品（懐中電灯、武器等）の制御 |
| `Controllers/Motion/` | （複数） | 物理的な動き・モーション処理 |
| `Controllers/Player/PlayerStateMachine.cs` | PlayerStateMachine | プレイヤー状態管理（FSM） |
| `Controllers/Player/PlayerHealth.cs` | PlayerHealth | HP 管理 |
| `Controllers/Player/FootstepsSystem.cs` | FootstepsSystem | 足音・地面材質連動 |
| `Controllers/Player/PlayerComponent.cs` | PlayerComponent | プレイヤー基底コンポーネント |
| `Controllers/Player/FSM/` + `PlayerStates/` | （複数 State クラス） | Idle / Walk / Run / Crouch / Jump / etc. |

### 2.2 Core — ゲームコア機構
| パス | 主要クラス | voice_horror での用途 |
|---|---|---|
| `Core/AI/NPCStateMachine.cs` | NPCStateMachine | **3 幽霊 AI のベース** |
| `Core/AI/AIStates/` | （複数 State クラス） | Patrol / Chase / Investigate 等 |
| `Core/AI/NPCHealth.cs` | NPCHealth | 幽霊の HP（文書読破前は無敵にカスタム） |
| `Core/AI/NPCBodyPart.cs` | NPCBodyPart | 部位別ダメージ |
| `Core/AI/Waypoints/` | （複数） | 巡回パターン |
| `Core/Inventory/Item.cs` | Item | **文書アイテム** |
| `Core/Inventory/Behaviour/` | （複数） | アイテム動作（読む、使う、装備） |
| `Core/Inventory/Slot/` | （複数） | スロット管理 |
| `Core/Dialogue/DialogueSystem.cs` | DialogueSystem | **少女の電話セリフ表示** |
| `Core/Dialogue/DialogueTrigger.cs` | DialogueTrigger | 会話開始トリガー |
| `Core/Dialogue/DialogueEvents.cs` | DialogueEvents | 会話イベント発火 |
| `Core/Dialogue/DialogueSpeechText.cs` | DialogueSpeechText | テキスト表示 |
| `Core/Dialogue/DialogueBinder.cs` | DialogueBinder | データバインディング |
| `Core/Game/GameManager.cs` | GameManager | **シングルトン中央管理** |
| `Core/Game/LevelManager.cs` | LevelManager | レベル切替 |
| `Core/Game/PlayerManager.cs` | PlayerManager | プレイヤー登録 |
| `Core/Game/PlayerPresenceManager.cs` | PlayerPresenceManager | プレイヤー存在通知（AI 用） |
| `Core/Game/Jumpscare/` | （複数） | **ジャンプスケア演出** |
| `Core/Game/MainMenuManager.cs` | MainMenuManager | メインメニュー |
| `Core/Game/TipsManager.cs` | TipsManager | ヒント表示 |
| `Core/Game/Localization/` | （複数） | 多言語対応 |
| `Core/Game/Modules/` | （複数） | プラガブルモジュール |
| `Core/Health/BaseHealthEntity.cs` | BaseHealthEntity | HP 基底 |
| `Core/Health/BaseBreakableEntity.cs` | BaseBreakableEntity | 破壊可能基底 |
| `Core/SaveGame/SaveGameManager.cs` | SaveGameManager | **セーブ全体管理** |
| `Core/SaveGame/SaveGameReader.cs` | SaveGameReader | セーブ読込 |
| `Core/SaveGame/SaveableBehaviour.cs` | SaveableBehaviour | セーブ可能コンポーネント基底 |
| `Core/SaveGame/SaveableObject.cs` | SaveableObject | セーブ対象オブジェクト |
| `Core/SaveGame/SaveableExtensions.cs` | SaveableExtensions | 拡張メソッド |
| `Core/SaveGame/SerializableEncryptor.cs` | SerializableEncryptor | **セーブデータ暗号化** |
| `Core/Input/` | （複数） | New Input System ラッパ |
| `Core/Objectives/` | （複数） | クエスト/目標管理 |
| `Core/Options/` | （複数） | 設定画面バックエンド |
| `Core/Puzzle/` | （複数） | パズル基盤 |

### 2.3 Interact — インタラクション系
| パス | 機能 | voice_horror での用途 |
|---|---|---|
| `Interact/Items/` | アイテムピックアップ | 文書ピックアップ |
| `Interact/Hiding/` | 隠れる場所 | クローゼット隠れ |
| `Interact/Lights/` | ライト切替 | 懐中電灯・電球 |
| `Interact/Breakable/` | 破壊可能オブジェクト | 窓、瓶 |
| `Interact/Other/` | 一般インタラクション | ドア、引き出し |
| `Interact/CCTV/` | 監視カメラ | 使う場合あり（演出） |
| `Interact/Elevator/` | エレベーター | 洋館設定で使う？ |
| `Interact/PowerGenerator/` | 電源 | 停電演出 |
| `Interact/Radio/` | ラジオ | 演出BGM |
| `Interact/VHS/` | VHS テープ | 演出（記録） |
| `Interact/Zipline/` | ジップライン | おそらく未使用 |

### 2.4 UI — UI コンポーネント
| パス | 機能 |
|---|---|
| `UI/Menu/` | メインメニュー UI |
| `UI/Interact/` | インタラクションプロンプト |
| `UI/Options/` | オプション画面 |
| `UI/ControlInfo/` | コントロール表示 |
| `UI/BackgroundFader.cs` | フェード演出 |
| `UI/HotspotKey.cs` | ホットスポット表示 |
| `UI/ItemPickupElement.cs` | ピックアップ通知 |
| `UI/SpritesheetAnimation.cs` | スプライトアニメ |
| `UI/LayoutElementResizer.cs` | レイアウト調整 |

### 2.5 その他
| パス | 用途 |
|---|---|
| `Animation/` | アニメーション関連スクリプト |
| `Attributes/` | カスタム属性（Inspector 拡張） |
| `Interfaces/` | インターフェース定義 |
| `Misc/` | 雑多なユーティリティ |
| `RenderFeatures/` | URP RenderFeature |
| `Trigger/` | 各種トリガー |
| `Utilities/` | 共通ユーティリティ |

---

## 3. voice_horror で重点的に拡張・カスタマイズすべき箇所

### 3.1 NPCStateMachine（幽霊 AI）
- **3 体の性格を State Pattern または BT で実装**
  - マギー（臆病）: プレイヤーに気付くと逃げる
  - アルフレッド（勇敢）: 視認直後に追跡
  - マークス（賢い）: 罠を仕掛ける、待ち伏せ
- **無敵化**: 該当文書 4 個読破まで `NPCHealth` を damage 無効化
- **ボイス強化応答**: 外部からのパラメータ強化を受信するインターフェース

### 3.2 DialogueSystem（少女の電話）
- **TTS 動的呼び出し**: 事前録音ではなく Qwen3-TTS へ IPC
- **声混じり演出**: 終盤、プレイヤー録音を blend → 少女のセリフに重ねる
- **オフトリガー**: 声色変更検出時、「電話を切る」イベント発火

### 3.3 Inventory（文書システム）
- **文書アイテム派生**: `Item` を継承し `DocumentItem` クラスを作成
- **完読フラグ**: 12 個（4×3）のフラグ管理、ScriptableObject 化
- **読む UI**: ページめくり、フォント、ハイライトで没入感

### 3.4 SaveGame（録音 + 進捗）
- **録音 wav**: SaveableObject で保存、暗号化（SerializableEncryptor）
- **エンディング判定用**: 録音蓄積を 1 つの統合 wav として保持

---

## 4. 自前実装すべき新機能（UHFPS にない）

| 機能 | 配置先（予定） | 依存 |
|---|---|---|
| `VoiceRecorder` | `Assets/voice_horror/Voice/VoiceRecorder.cs` | UnityEngine.Microphone |
| `VoiceSimilarityAnalyzer` | `Assets/voice_horror/Voice/VoiceSimilarityAnalyzer.cs` | MFCC 計算ライブラリ |
| `VoiceIntensityDetector` | `Assets/voice_horror/Voice/VoiceIntensityDetector.cs` | UnityEngine.Microphone |
| `GhostAmplifier` | `Assets/voice_horror/AI/GhostAmplifier.cs` | NPCStateMachine 拡張 |
| `TTSClient`（Qwen3 IPC） | `Assets/voice_horror/Voice/TTSClient.cs` | ComfyUI WebSocket / プロセス起動 |
| `EndingJudgment` | `Assets/voice_horror/Game/EndingJudgment.cs` | VoiceSimilarityAnalyzer |
| `DocumentReadProgress` | `Assets/voice_horror/Documents/DocumentReadProgress.cs` | UHFPS Inventory |

これらは **feature-db に登録**して TDD で実装する候補。

---

## 5. このドキュメントの更新規約

- UHFPS のバージョンアップで構成が変わった時は、`ls Runtime/` の出力を再取得して本ドキュメントを更新
- voice_horror が UHFPS の特定クラスを継承/拡張する場合、§ 3 にエントリを追加
- 新規自前実装は § 4 に追記、`feature-db` 登録時に `dependencies` フィールドで本ファイルを参照
