# UI Structure 指示フォーマット

このフォーマットを使用して、UI画面の構成をAIに指示する。
UI Toolkit (UXML/USS) での実装を前提とする。

## フォーマット

```
# UI: [画面名]

## Layout
- [要素名] (type: [VisualElement|Button|Label|TextField|...])
  - style: [USSクラス名]
  - text: "[表示テキスト]"
  - binding: [バインディングパス]
  - children:
    - [子要素名] (type: [タイプ])
      - ...

## Styles (USS)
- .[クラス名]:
  - width: [値]
  - height: [値]
  - flex-direction: [row|column]
  - ...

## Events
- [要素名].[イベント名] → [ハンドラ説明]

## Data Binding
- [要素名] ← [データソース].[プロパティ]
```

## 使用例

```
# UI: MainMenu

## Layout
- Root (type: VisualElement)
  - style: main-menu-root
  - children:
    - TitleLabel (type: Label)
      - style: title-text
      - text: "Game Title"
    - ButtonContainer (type: VisualElement)
      - style: button-container
      - children:
        - StartButton (type: Button)
          - style: menu-button
          - text: "Start Game"
        - SettingsButton (type: Button)
          - style: menu-button
          - text: "Settings"
        - QuitButton (type: Button)
          - style: menu-button, quit-button
          - text: "Quit"
    - VersionLabel (type: Label)
      - style: version-text
      - text: "v1.0.0"

## Styles (USS)
- .main-menu-root:
  - width: 100%
  - height: 100%
  - align-items: center
  - justify-content: center
  - background-color: rgba(0,0,0,0.8)

- .title-text:
  - font-size: 48px
  - color: white
  - margin-bottom: 40px

- .button-container:
  - flex-direction: column
  - align-items: center

- .menu-button:
  - width: 200px
  - height: 50px
  - margin: 8px
  - font-size: 20px

- .quit-button:
  - color: #ff4444

## Events
- StartButton.clicked → シーン "Level_01" をロード
- SettingsButton.clicked → SettingsPanel を表示
- QuitButton.clicked → Application.Quit()
```

## 注意事項
- type は UI Toolkit の VisualElement 派生クラス名を使用
- style は USS クラス名（複数指定はカンマ区切り）
- binding は SerializedObject のプロパティパスを指定
- USS の詳細プロパティはUnity UI Toolkitドキュメント参照
