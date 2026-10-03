# データの出典・ライセンス・版

> 旧版 (walk15、2026-10-03 公開、駅の縄張りマップに置き換え) の記録です。

公開されていることと、自由に再配布できることは別です。データを足すときは、取得の前にこの表を埋めます。
生データ・中間ファイル・生成物は Git に入れません (`data/` と `web/*/data/` は Git 管理外)。
取得コマンドは各ファイルの隣に `*.provenance.json` (URL・大きさ・SHA-256・取得日時 UTC) を書きます。

確認日: 2026-10-03

## 国土数値情報 鉄道データ (N02)

| 項目 | 内容 |
|---|---|
| 正式名称・提供者 | 国土数値情報 鉄道データ、国土交通省 |
| 配布ページ | https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2025.html |
| 版 | 2025 年度 (令和 7 年度) 版、2025-12-31 時点 |
| ファイル | `N02-25_GML.zip` — https://nlftp.mlit.go.jp/ksj/gml/data/N02/N02-25/N02-25_GML.zip |
| 大きさ・SHA-256 | 14,903,774 bytes、`aaf76af133b2e771e538fabc4646d2e443dc1d5a67b221382a28d744e706cc9f` |
| 取得日時 (UTC) | 2026-10-03T09:28:27+00:00 |
| 利用条件 | 2020 年以降の版はオープンデータ (CC BY 4.0) と配布ページに記載 |
| 出典表記 | 「国土数値情報（鉄道データ）（国土交通省）を加工して作成」 |
| 使う部分 | `UTF-8/N02-25_Station.geojson` (駅。路線ごとのホームの線、JGD2011 経緯度) |

使う属性:

| 属性 | 意味 | 使い方 |
|---|---|---|
| `N02_001` | 鉄道区分コード | `13` (鋼索鉄道 = ケーブルカー。高尾山・御岳山) を除外 |
| `N02_003` / `N02_004` | 路線名 / 運営会社 | 表示。`4号線丸ノ内線` のような番号の頭は表示で落とす |
| `N02_005` | 駅名 | 表示 |
| `N02_005c` | 駅コード | 路線ごとの駅の ID。同じコードの線が複数の地物に分かれていることがあるので、まとめてから使う |
| `N02_005g` | グループコード | 「300m 以内で同じ名前の駅」をまとめたもの。これを「1 駅」として数える |

注: 東京駅の京葉線ホームは別のグループ (`003785`) になっている。

## 国土数値情報 行政区域データ (N03)

| 項目 | 内容 |
|---|---|
| 正式名称・提供者 | 国土数値情報 行政区域データ、国土交通省 |
| 配布ページ | https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html |
| 版 | 2026 年 (令和 8 年) 1 月 1 日時点、東京都 |
| ファイル | `N03-20260101_13_GML.zip` — https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2026/N03-20260101_13_GML.zip |
| 大きさ・SHA-256 | 13,153,227 bytes、`94f10b26256566db970dd74b09d614f059c1e8a432f9244ac9c4add76c32ff16` |
| 取得日時 (UTC) | 2026-10-03T09:28:30+00:00 |
| 利用条件 | オープンデータ (CC BY 4.0) と配布ページに記載 |
| 出典表記 | 「国土数値情報（行政区域データ）（国土交通省）を加工して作成」 |
| 使い方 | `N03_007` (市区町村コード) で島しょ部 9 町村と所属未定地 (`13000`) を除き、残りを合わせて対象範囲にする (1,782.59 km²) |

注: この版では東京都の `N03_002` (支庁名) がすべて空のため、支庁名では島しょ部を除けない。

## Overture Maps transportation (segment)

| 項目 | 内容 |
|---|---|
| 提供者 | Overture Maps Foundation |
| 案内 | https://docs.overturemaps.org/ 、出典: https://docs.overturemaps.org/attribution/ |
| 版 | release `2026-09-23.1` |
| 取得元 | `s3://overturemaps-us-west-2/release/2026-09-23.1/theme=transportation/type=segment/*.parquet` (認証なし) |
| 取り出し方 | DuckDB で `subtype = 'road'` かつ bbox (経度 138.90891〜139.95239、緯度 35.47125〜35.92815) に重なる行。列は `id, subtype, class, subclass, connectors, access_restrictions, road_flags, geometry` |
| 保存したファイル | `data/raw/overture/2026-09-23.1/segment_tokyo.parquet`、1,107,926 行、119,520,928 bytes、SHA-256 `984d3765878b31b41f3c9d6d65b11afa9fd50a72a737798de04746626d56f69e` |
| 取得日時 (UTC) | 2026-10-03T09:33:47+00:00 |
| 利用条件 | transportation テーマは ODbL。© OpenStreetMap contributors。テーマ全体の出典として TomTom のデータも挙げられている |
| 出典表記 | 「© OpenStreetMap contributors, Overture Maps Foundation」(画面と README に表示) |
| 再配布 | このデータから作った表・輪郭・塗り (派生データベース) は ODbL で提供する |
| 保存期間 | Overture は公開から約 60 日で古い release を消す。消えたあとの再現は新しい release で行い、版を書き換える |

## 背景地図 (画面がブラウザから直接読む。取得・保存はしない)

| 項目 | 内容 |
|---|---|
| OpenFreeMap | https://openfreemap.org/ 。OpenStreetMap のデータによるベクトル地図。登録・API キー・Cookie なし、回数制限なしと記載。利用規約 https://openfreemap.org/tos/ 。表記「OpenFreeMap © OpenMapTiles Data from OpenStreetMap」 |
| 地理院タイル (シームレス空中写真) | https://maps.gsi.go.jp/development/ichiran.html 。国土地理院の利用規約に従い、出典「地理院タイル」を表示 |

## 使わないことにしたもの

- OpenStreetMap の公式タイル (tile.openstreetmap.org): 利用方針で大量の利用が禁じられており、ブログで人が集まると問題になりうるため。
- 住所検索 API (国土地理院など): 入力した住所が外部へ送られるため、v1 では入れない。
