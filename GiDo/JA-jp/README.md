<p align="center"><img src="banner.svg" alt="FODB" width="100%"></p>

<p align="center">
<a href="../../README.md"><img src="../../docs/lang/EN-en-off.svg" height="26" alt="English"></a>
<a href="../../GiDo/RU-ru/README.md"><img src="../../docs/lang/RU-ru-off.svg" height="26" alt="Русский"></a>
<a href="../../GiDo/ZH-cn/README.md"><img src="../../docs/lang/ZH-cn-off.svg" height="26" alt="简体中文"></a>
<a href="../../GiDo/ES-es/README.md"><img src="../../docs/lang/ES-es-off.svg" height="26" alt="Español"></a>
<a href="../../GiDo/HI-in/README.md"><img src="../../docs/lang/HI-in-off.svg" height="26" alt="हिन्दी"></a>
<a href="../../GiDo/AR-sa/README.md"><img src="../../docs/lang/AR-sa-off.svg" height="26" alt="العربية"></a>
<a href="../../GiDo/FR-fr/README.md"><img src="../../docs/lang/FR-fr-off.svg" height="26" alt="Français"></a>
<a href="../../GiDo/BN-bd/README.md"><img src="../../docs/lang/BN-bd-off.svg" height="26" alt="বাংলা"></a>
<a href="../../GiDo/PT-br/README.md"><img src="../../docs/lang/PT-br-off.svg" height="26" alt="Português"></a>
<a href="../../GiDo/UR-pk/README.md"><img src="../../docs/lang/UR-pk-off.svg" height="26" alt="اردو"></a>
<a href="../../GiDo/ID-id/README.md"><img src="../../docs/lang/ID-id-off.svg" height="26" alt="Indonesia"></a>
<a href="../../GiDo/DE-de/README.md"><img src="../../docs/lang/DE-de-off.svg" height="26" alt="Deutsch"></a>
<a href="../../GiDo/JA-jp/README.md"><img src="../../docs/lang/JA-jp-on.svg" height="26" alt="日本語"></a>
<a href="../../GiDo/TR-tr/README.md"><img src="../../docs/lang/TR-tr-off.svg" height="26" alt="Türkçe"></a>
<a href="../../GiDo/KO-kr/README.md"><img src="../../docs/lang/KO-kr-off.svg" height="26" alt="한국어"></a>
<a href="../../GiDo/VI-vn/README.md"><img src="../../docs/lang/VI-vn-off.svg" height="26" alt="Tiếng Việt"></a>
<a href="../../GiDo/IT-it/README.md"><img src="../../docs/lang/IT-it-off.svg" height="26" alt="Italiano"></a>
<a href="../../GiDo/PL-pl/README.md"><img src="../../docs/lang/PL-pl-off.svg" height="26" alt="Polski"></a>
<a href="../../GiDo/UK-ua/README.md"><img src="../../docs/lang/UK-ua-off.svg" height="26" alt="Українська"></a>
<a href="../../GiDo/TH-th/README.md"><img src="../../docs/lang/TH-th-off.svg" height="26" alt="ไทย"></a>
</p>

<p align="center"><a href="https://github.com/Arkomiko/Fruity-Organizer-DataBase/releases/latest"><b>⬇ FODB.exe をダウンロード</b></a></p>

FL Studio のプラグインデータベース用ポータブル整理ツールです。メーカー別、用途別、またはその両方でプラグインをフォルダーに整理し、FL Studio になじむ見た目で動作します。

<p align="center"><img src="../../docs/demo-en.gif" alt="FODB" width="100%"></p>

## 機能

- メーカー別、用途別、または任意の順で階層化：メーカー\用途 または 用途\メーカー
- 各プラグインの用途を判定：リバーブ、EQ、ダイナミクス、シンセなど全 22 種類
- 用途、メーカー、形式、ビット、状態、ファイル日付、サイズなどで絞り込み
- 現在の FL Studio テーマにリアルタイムで追従
- 自動バックアップ、ワンクリックで元に戻す、データベースフォルダーの外には何も出ません
- インストール不要の 9 MB の単一ファイル。設定はその隣に保存
- 20 のインターフェース言語と、配置、ホットキー、スケール、フォント、色などの設定

## クイックスタート

1. FODB.exe をダウンロードして実行します。プラグインデータベースは自動で見つかります。
2. フォルダー構成を選び、ソースとフィルターをオン・オフします。
3. 「プラグインを整理」を押してプレビューを確認し、FL Studio のプラグインブラウザーを更新します。

## フォルダー構成

<p align="center"><img src="workflow.svg" alt="フォルダー構成" width="100%"></p>

プリセットを選ぶか、次の要素で独自のテンプレートを書けます：

```text
{vendor}  {purpose}  {format}  {bits}  {letter}  {kind}

{vendor}\{purpose}
{purpose}\{vendor}
USER\{format}\{vendor}
```

## フィルター

フィルターメニューで値を選ぶか、検索欄に条件を入力します：

```text
purpose:reverb,delay                 reverb OR delay
vendor:"plugin alliance" -format:vst  one vendor, without VST2
organized:no kind:synth               synths not organized yet
age:30d bits:64                       64-bit, dated in the last 30 days
```

## FL Studio テーマ

<p align="center"><img src="themes.svg" alt="FL Studio テーマ" width="100%"></p>

FODB は現在のテーマを読み取り、FL Studio で変更すると配色を更新します。基本色は非常に近いものの、ピクセル単位で同一ではありません。

## 安全性

- プラグイン本体は変更されません。Installed フォルダーで変わるのは New 一覧だけです。整理したプラグインは一覧から外れ、この動作はオフにできます。
- 実行はすべて元に戻せ、削除したファイルはごみ箱に移動します。
- 変更のたびにデータベースの ZIP バックアップを作成します。最新 40 個を保持し、数は変更できます。

## 独自ルール

「設定」タブまたは FODB.json でルールを追加し、正規表現で名前やメーカーごとに用途を指定できます：

```json
"purpose_rules": [
  { "purpose": "drums", "name": "kick|808" },
  { "purpose": "vocal", "vendor": "antares" }
]
```

## ソースからビルド

Windows と Python 3.13 が必要です。本体は標準ライブラリのみを使用します。

```powershell
./build.ps1
```

## クレジット

Magabes と貢献者による FL Studio Automatic Plugin Organizer をベースにしています（MIT ライセンス）。

独立したプロジェクトであり、Image-Line とは無関係です。FL Studio は Image-Line の商標です。
