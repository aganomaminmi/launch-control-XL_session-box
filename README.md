# LaunchControlXL_SessionBox

Novation Launch Control XL 用の Ableton Live 12 カスタム MIDI Remote Script。
セッションビューのハイライトボックス表示、ミキサー制御、デバイスパラメータの直接マッピング（24ノブ）を実装。

## 機能

- セッションビューにハイライトボックス（選択範囲）を表示
- フェーダー: トラックボリューム
- ノブ Row 1: Send A / デバイスパラメータ 1-8
- ノブ Row 2: Send B / デバイスパラメータ 9-16
- ノブ Row 3: Pan / デバイスパラメータ 17-24
- Track Focus: トラック選択（LEDでフォーカス表示）
- Track Control: Mute / Solo / Record Arm（サイドボタンでモード切替）
- Device モード: ノブ24個でデバイスパラメータを直接制御
- Device ホールド + Track Select 左右: デバイス切替
- ノブLED: トラックカラー表示（デバイスモード時はアンバー）
- グループトラック折りたたみ対応（visible_tracks）

## 配置方法

1. このリポジトリのファイルを以下のディレクトリにコピー:

```
~/Music/Ableton/User Library/Remote Scripts/LaunchControlXL_SessionBox/
```

配置後のディレクトリ構成:

```
Remote Scripts/
  LaunchControlXL_SessionBox/
    __init__.py
    LaunchControlXL_SessionBox.py
```

2. Ableton Live を起動（または再起動）
3. `Preferences` > `Link, Tempo & MIDI` > `Control Surface` で `LaunchControlXL_SessionBox` を選択
4. Input / Output に Launch Control XL を設定

## 要件

- Ableton Live 12
- Novation Launch Control XL（Factory Template使用、MIDI Channel 9）
