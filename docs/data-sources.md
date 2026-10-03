# データの出典・ライセンス・版 (駅の縄張りマップ 【首都圏編】)

公開されていることと、自由に再配布できることは別です。データを足すときは、取得の前にこの表を埋めます。
生データ・中間ファイル・生成物は Git に入れません (`data/` と `web/data/` は Git 管理外)。

確認日: 2026-10-04 (公式の配布ページ・規約本文・測量成果Q&Aを再確認。後段に確認結果と未確定事項を記載)

## 生データの入手のしかた

東京版の初回では新しいダウンロードをしていません。同じ作者の [rail-gap-map](https://github.com/isshiki/rail-gap-map) が
2026-10-03 に取得した生データを `uv run eki-walk import-raw --from ../rail-gap-map` で写し、
rail-gap-map の取得記録 (`data/raw/manifest.json`) の SHA-256 と一致することを確かめています。
写した記録は `data/raw/manifest.json` (`copied_from`・`copied_utc`) に残ります。
各データの確認の記録は rail-gap-map の `docs/sources/` (commit `4176263`) にもあります。
首都圏への拡大時に追加取得したABR 6件は、後段の表に別途記録しています。2026-10-04の引き継ぎ確認ではデータの追加取得は行っていません。

| キー | ファイル | 大きさ (bytes) | SHA-256 | 元の取得日時 (UTC) |
|---|---|---:|---|---|
| `osm-kanto` | `kanto-261001.osm.pbf` | 515,684,430 | `5e0b1bec8d8754a18db3950c6a39e4921e8c19069106a1ac038731f3d250ca83` | 2026-10-03T09:29:33Z |
| `n02` | `N02-25_GML.zip` | 14,903,774 | `aaf76af133b2e771e538fabc4646d2e443dc1d5a67b221382a28d744e706cc9f` | 2026-10-03T09:28:23Z |
| `n03-11` | `N03-20260101_11_GML.zip` | 3,574,165 | `f45239da019b4c77330a752031b758d3a6125c6a6ff49fe4e0be930857ab3643` | 2026-10-03T09:28:23Z |
| `n03-12` | `N03-20260101_12_GML.zip` | 8,132,153 | `558348445ef9c8fa609010759061833aff8c009fab98860c03e1bff59ad18d7c` | 2026-10-03T09:28:23Z |
| `n03-13` | `N03-20260101_13_GML.zip` | 13,153,227 | `94f10b26256566db970dd74b09d614f059c1e8a432f9244ac9c4add76c32ff16` | 2026-10-03T09:28:24Z |
| `n03-14` | `N03-20260101_14_GML.zip` | 5,370,610 | `27ab5aa2982fc6fe81e9c0b08ca75d18177e8228527b2e602ce803e681e7e561` | 2026-10-03T09:28:24Z |
| `abr-town-13` | `mt_town_pref13.csv.zip` | 83,827 | `58f62944afa4d641880ea255838c8c0be2cf5f363eb97e27e3173e3eecc493b3` | 2026-10-03T09:28:24Z |
| `abr-town-pos-13` | `mt_town_pos_pref13.csv.zip` | 84,132 | `06c42c5a1beb3f2606c1816893fe7bc8efa7d5edf1a8c7a366e8a04bef87c0a8` | 2026-10-03T09:28:24Z |

### 首都圏への拡大で取得したもの

| キー | ファイル | 大きさ (bytes) | SHA-256 | 取得日時 (UTC) |
|---|---|---:|---|---|
| `abr-town-11` | `mt_town_pref11.csv.zip` | 144,717 | `7bf74aaca29a3f9a1d3e24a46c8aa3af90ff3d3873b711012ca0905a0408e580` | 2026-10-03T14:16:22Z |
| `abr-town-pos-11` | `mt_town_pos_pref11.csv.zip` | 111,586 | `51065c3e86d57cd570af1bbfcd412b82e131a9bc95c8277a774b0c634c4513b5` | 2026-10-03T14:16:22Z |
| `abr-town-12` | `mt_town_pref12.csv.zip` | 207,578 | `99a92102f8f0035356d12b45bed7df6b23c84e662666c7131abd2b72fc6dd6d5` | 2026-10-03T15:55:59Z |
| `abr-town-pos-12` | `mt_town_pos_pref12.csv.zip` | 124,662 | `da84dd70f0d4028a54f9fb1d43595e270da99cae56535c84dc7f763f7c52f396` | 2026-10-03T15:55:59Z |
| `abr-town-14` | `mt_town_pref14.csv.zip` | 130,762 | `9a60a80f840771fc4bbfa07754206d83755e9eb9abb232666792f89f0e9dc1d6` | 2026-10-03T16:27:10Z |
| `abr-town-pos-14` | `mt_town_pos_pref14.csv.zip` | 87,036 | `08747391383da727e5fcd5a39827ea0a69982157a3efd898ec48ffd378cc6964` | 2026-10-03T16:27:10Z |

取得は `uv run eki-walk fetch <キー>` (取得元は `configs/sources.toml`)。

## OpenStreetMap 関東抽出 (Geofabrik)

| 項目 | 内容 |
|---|---|
| 配布 | https://download.geofabrik.de/asia/japan/kanto.html (`kanto-261001.osm.pbf`、2026-10-01 の日付付きファイル) |
| 利用条件 | Open Database License (ODbL) 1.0 — https://www.openstreetmap.org/copyright |
| 出典表記 | © OpenStreetMap contributors (地図の右下と「このマップについて」) |
| 使い方 | 歩ける道 (`ekiwalk` の規則: 自動車専用道路・`foot=no`・立入禁止などを除く) と水面。駅名の読み (`name:ja-Hira`) を検索に使う |
| 再配布 | 縄張り・帯・15 分超・15 分圏の輪郭・格子ごとの道のり、`places.json` の駅名の読みは OSM の派生データベースとして ODbL 1.0 で提供する |

## 国土数値情報 鉄道データ (N02) / 行政区域データ (N03)

| 項目 | 内容 |
|---|---|
| 提供者 | 国土交通省 |
| 版 | N02: 2025 年度版 (2025-12-31 時点)。N03: 2026 年 (2026-01-01 時点)、埼玉・千葉・東京・神奈川 |
| 利用条件 | オープンデータ (CC BY 4.0) と各配布ページに記載 (N02: 2020 年以降の版、N03: 2026 年版)。利用約款 https://nlftp.mlit.go.jp/ksj/other/agreement.html : 出典に当該ページの URL を付け、加工したときはその旨を書く。国が作成したかのように公表しない |
| 出典表記 | 「国土数値情報（鉄道データ）」（国土交通省）（https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2025.html）、「国土数値情報（行政区域データ）」（国土交通省）（https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html）を加工して作成 |
| 使い方 | N02: 駅 (ホームの線)、グループコードと駅名で駅をまとめる。N03: 陸地と表示範囲 (東京都 (島しょ 9 町村を除く)・埼玉県・千葉県・神奈川県)。縄張りを切る線として、5m の誤差で単純化して使う |
| 測量法 | N03 の配布ページには国土交通省の作成に係る承認番号 R 7JHf 351 がある。このマップはN03の面を単純化して縄張りのクリップに使い、`aoi.geojson` も出力している。「背景図を複製していないから申請不要」とは断定できない。著作権の許諾と測量法の手続は別であり、後段の未確定事項を参照 |

## アドレス・ベース・レジストリ (デジタル庁) 町字マスター (東京都・埼玉県・千葉県・神奈川県)

| 項目 | 内容 |
|---|---|
| 配布 | https://dataset.address-br.digital.go.jp/ |
| 利用条件 | 公共データ利用規約 (第1.0版) (PDL1.0、CC BY 4.0 と互換)。利用規約 https://www.digital.go.jp/policies/base_registry_address_tos (2026-05-29 更新、2026-10-04 に確認)。rail-gap-map の記録 (2026-10-03) は CC BY 4.0 としていたが、規約の本文は PDL1.0。使うのは町字マスターだけで、登記所備付地図データ由来の地番マスター (別の規約) は使わない |
| 出典表記 | 「アドレス・ベース・レジストリ」（デジタル庁）（https://www.digital.go.jp/policies/base_registry_address）を加工して作成 |
| 使い方 | 町丁目の名前・よみ・代表点を、ブラウザの中だけで動く検索に使う (`places.json`)。駅名の読みが OSM にないとき、同じ名前の町名の読みでも補う |

`places.json` は ABR (PDL1.0)・国土数値情報 (CC BY 4.0) と OSM (ODbL 1.0、駅名の読み) を合わせたもの。生成データベースはODbL 1.0で提供するが、個々の内容の出典・元の利用条件も保持する。「出典を示すだけでCC BY 4.0とODbLが無条件に互換」とは扱わない。読みのうち OSM にも ABR にもなかった 147 駅分は作者が補った (`configs/station-readings.toml`、Apache-2.0)。

`configs/sources.toml` のABR 8件の規約名もPDL1.0へ修正した。`data/raw/manifest.json` の取得記録 (URL・日時・SHA-256) は書き換えていない。データの再取得は行わず、既存データから4都県の territory と combine を再実行した。現在の配布条件はこの文書と公開用READMEで明示する。

## 背景地図 (画面がブラウザから直接読む。取得・保存はしない)

| 項目 | 内容 |
|---|---|
| OpenFreeMap | https://openfreemap.org/ 。OpenStreetMap のデータによるベクトル地図。無料・登録不要・商用可。表記「OpenFreeMap © OpenMapTiles Data from OpenStreetMap」が必須 (MapLibre が地図の右下に出す)。POI と道路番号 (shield) は表示しない |
| 地理院タイル (全国最新写真 (シームレス)) | https://maps.gsi.go.jp/development/ichiran.html 。国土地理院コンテンツ利用規約 (PDL1.0) と各タイルの第三者の条件に従う。地理院タイルへのリンクに加え、ズーム9〜13のLandsat8・GEBCO、ズーム2〜8のNASA/USGS LP DAACも出典に記載する。GRUS画像 (© Axelspace) の範囲は南鳥島で、本マップの4都県には含まれない。出典は地図の右下と「このマップについて」に表示する。リアルタイムで地理院サーバーから読む方式は、国土地理院Q&A Q1-12で出典明示のみ・申請不要とされる |
| MapLibre GL JS 6.11.2 (BSD-3-Clause)、proj4js 2.22.0 (MIT) | jsDelivr からブラウザが読む。このリポジトリには入れない |

## 2026-10-04 の確認結果と再配布条件

- [N02 2025年度](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2025.html)・[N03 2026年](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html) は、それぞれのデータの許諾欄がCC BY 4.0。サイト全般の[利用規約](https://nlftp.mlit.go.jp/ksj/other/agreement.html)は2026-03-23施行のPDL1.0だが、個別のデータに明記されたCC BY 4.0を優先して記載する。
- [ABRの規約](https://www.digital.go.jp/policies/base_registry_address_tos)はPDL1.0。利用している町字マスターと町字マスター位置参照はこの条件に従う。地番マスター等の別規約の対象は使用していない。[PDL1.0本文](https://www.digital.go.jp/resources/open_data/public_data_license_v1.0)の1.7(3)はCC BY 4.0に従う利用も認める。出典URL・加工したこと・加工主体 (eki-walk作者) を保持する。
- [OSMの著作権ページ](https://www.openstreetmap.org/copyright)と[ODbL 1.0本文](https://opendatacommons.org/licenses/odbl/1-0/)を確認。生成データベースにODbL 1.0を適用し、© OpenStreetMap contributorsと規約リンクを添える。ODbLの2.4は個々の内容の別の権利を置き換えない。4.6に従い、公開時は機械可読のデータも無料で入手できるようにする。全体は[gh-pagesのZIP](https://github.com/isshiki/eki-walk/archive/refs/heads/gh-pages.zip)、個別JSONは公開ページの `data/` 以下から取得できる (ZIPの取得は実際には行っていない)。
- CC BY 4.0側の出典・加工表示・規約リンクも配布物に残す。[OSMFの互換性説明](https://osmfoundation.org/wiki/Licence/Licence_Compatibility)はCC BYデータのOSM本体への取り込みに追加許諾が必要としている。このプロジェクトはOSM本体へ取り込むものではなく、各内容の元の条件を併記して独自の派生データベースを配布する。追加の権利を一括でODbLへ再許諾したと誤解させない。
- [OpenFreeMap](https://openfreemap.org/)は商用利用も許可し、OpenMapTilesとOSMの出典が必要。MapLibreによる自動表記を維持する。[地理院の規約](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html)と[タイル一覧](https://maps.gsi.go.jp/development/ichiran.html)の個別出典も維持する。

### 未確定: N03 の測量法上の手続

N03を背景の画像として複製していないことは実装から確認できるが、位置座標を持つ行政区域・海岸線を使い、面の外周と `aoi.geojson` を公開している。サイトの「背景図を含む調査成果」の説明は国土調査の成果についてのもので、これだけでN03の手続不要を判断できない。[国土地理院Q&A](https://www.gsi.go.jp/LAW/2930-qa.html) Q1-24は複製承認を受けた成果品の二次利用でも申請が必要になり得ると説明している。

このため、CC BY 4.0の許諾を確認できたことと、測量法上の申請要否は分けて記録する。N03の発行元または国土地理院へ、版・入力データ・単純化とクリップの方法・公開するJSON (aoiを含む) を示して確認する必要がある。2026-10-04時点で問い合わせや申請は行っておらず、手続不要を確認済みとはしない。これは公式資料との照合結果であり、法的な確認を完了したものではない。

## 使わなくなったもの

旧版 walk15 で使った Overture Maps (release 2026-09-23.1) の記録は [walk15/data-sources.md](walk15/data-sources.md) にあります。
