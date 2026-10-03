# eki-walk

**This repository uses only publicly obtainable data. No proprietary company data is included.**

## 駅の縄張りマップ 【首都圏編】

住んでいる所 (これから住む所) が、**どの駅の勢力圏 (縄張り) に入るか**を、歩く道のりで示す地図です。対象は東京都 (島しょを除く)・埼玉県・千葉県・神奈川県です。対象の範囲はここまでとし、ほかの地域は要望があれば足します。

- 公開中: https://isshiki.github.io/eki-walk/
- 色分け = 歩く道のりでいちばん近い駅の範囲 (道路網のボロノイ分割)。となり合う縄張りは別の色。
- 斜線 = 2 番目に近い駅にも 15 分以内で行けて、差が 3 分以内の所 (どちらの駅もほぼ同じ近さ)。色の薄い所 = いちばん近い駅まで 15 分超。
- 地点をクリック (タップ) する・駅名 (読みがなも可) や住所で探す (住所は「○丁目」まで。番地まで入れても丁目までで探します)・現在地を使うと「ここは ○○駅の勢力圏 (徒歩 6 分)。△△駅 (12 分) の 15 分圏とも重なります」と出ます。
- 駅名をクリック (タップ) すると、その駅の縄張りと 15 分圏、縄張りの広さ・いちばん遠い所の徒歩分数を出します。
- 現在地の座標と検索文字を検索サービス等へ送信しません。背景地図・航空写真は表示範囲に応じたタイルを外部の配信元から読み込みます。

計算の土台 (道路網・最短路・格子・町丁目検索) は、同じ作者の [rail-gap-map](https://github.com/isshiki/rail-gap-map) の `ekiwalk` を使っています (commit を固定)。
そのため「いちばん近い駅」は rail-gap-map (最寄り駅までの等距離線の地図) と一致します。

- 設計: [docs/superpowers/specs/2026-10-03-territory-design.md](docs/superpowers/specs/2026-10-03-territory-design.md)
- 計算方法と限界: [docs/method.md](docs/method.md)
- データの出典と版: [docs/data-sources.md](docs/data-sources.md)
- 検証: [docs/validation.md](docs/validation.md)
- 旧版「徒歩15分 駅マップ」(walk15) の記録: [docs/walk15/](docs/walk15/)

## 作り方 (再現手順)

Python 3.11 以上と uv を使います。

```powershell
uv sync --locked
uv run pytest
node --test web/test/*.test.js         # 画面の住所の読み替え (Node.js 20 以上)
```

依存の初回取得 (`uv sync --locked`)、clone、生データの取得が必要な場合は、取得するファイル・取得元・大きさを示して作者の確認を取ってから行います。既存の `.venv` を使ってダウンロードを避ける場合は `uv --cache-dir .uv-cache run --offline --no-sync ...` で実行できます。一時フォルダの権限で pytest が止まる場合は `uv --cache-dir .uv-cache run --offline --no-sync pytest -q -p no:cacheprovider --basetemp=data/build/pytest-local-<新しい名前>` を使います (`--basetemp` は実行時に中身が消えるため、専用の未使用パスを指定)。

**手元の画面を確認するだけなら、生成済みの `web/data/` と `.venv` があれば再計算は不要です。**

```powershell
uv --cache-dir .uv-cache run --offline --no-sync scripts/serve.py
# http://127.0.0.1:8815/ を開く。編集後はブラウザを再読み込みし、終わったら Ctrl+C。
```

`scripts/serve.py` は現在の `web/` を localhost だけに公開します。ビルドとダウンロードは行いません。画面用データが不足していれば起動前に止まります。再生成中は地域のデータを入れ替えるため、ビルドとcombineが終わってから起動・再読み込みしてください。背景地図・航空写真・MapLibre/proj4 はブラウザから外部に読み込むため、画面の表示にはインターネット接続が必要です。

生データは、作者の公開プロジェクト rail-gap-map で取得済みのものを写して使います (SHA-256 を確かめます)。取得済みのローカル checkout を `import-raw --from` に指定してください。初回の4地域計算は、共有境界のため **全地域の admin を先に用意**する必要があります。共通スクリプトでその順序を管理します。

```powershell
uv run eki-walk import-raw --from ../rail-gap-map
uv run scripts/build_territories.py                 # 全地域の admin → 各地域 network … territory → combine
uv run scripts/build_territories.py --from territory # 道路網・格子が作成済みなら、4地域の描画だけ作り直す
uv run scripts/serve.py                             # http://127.0.0.1:8815/
```

`build_territories.py --dry-run` で実行順だけを確認できます。スクリプト自身はデータを取得しません。道路網の処理には DuckDB spatial 拡張も必要で、未導入なら取得が発生するため事前確認が必要です。1地域の `eki-walk build --config ...` は引き続き使えますが、共有境界を持つ4地域の territory と combine はまとめてやり直してください。

`configs/territory-oizumi.toml` は大泉学園町付近だけで計算する試運転用です。`uv run eki-walk combine --region oizumi-test --manifest regions-oizumi.json` のあと `http://127.0.0.1:8815/?manifest=data/regions-oizumi.json` で見られます。

## 公開 (GitHub Pages)

main にはコードと文書だけを置き、画面と生成データは `gh-pages` ブランチに置きます。`gh-pages` は履歴を持たず、公開のたびに 1 コミットで置き換えます。
push と `gh-pages` の差し替えは毎回作者の確認が必要です。公開の作業用フォルダはリポジトリの外に用意し、そこに画面と公開する4地域だけをコピーします。
中身は `web/` の画面 (`index.html`・`app.js`・`style.css`・`js/`・`walk15/index.html`)、`.nojekyll`、`web/data/` の `regions.json`・`overview.json`・`tokyo/`・`saitama/`・`chiba/`・`kanagawa/` (試運転用の `oizumi-test/` は除く) です。`data/README.md` と各地域の `README.md` には、データのライセンス表記 [docs/publish/data-README.md](docs/publish/data-README.md) を置きます (`{name}` を `overview.json` や地域名に置き換える)。

## ライセンス

- プログラムとオリジナルの文書: [Apache License 2.0](LICENSE)。`web/js/search.js` と `web/js/lookup.js` は rail-gap-map (Apache-2.0) から写したもの。
- 生成データ (縄張り・帯・15 分超・15 分圏の輪郭・格子ごとの道のり): OpenStreetMap から作った派生データベースのため [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) で提供します。© OpenStreetMap contributors。
- 駅・行政区域: 「国土数値情報（鉄道データ）」（国土交通省）（https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2025.html）、「国土数値情報（行政区域データ）」（国土交通省）（https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html）を加工して作成 (CC BY 4.0)。
- 検索データ (`places.json`): 「アドレス・ベース・レジストリ」（デジタル庁）（https://www.digital.go.jp/policies/base_registry_address）を加工して作成 (公共データ利用規約 第1.0版。CC BY 4.0 と互換)。駅名の読みの多くは OpenStreetMap の `name:ja-Hira` (ODbL 1.0)。
- 画面の背景: OpenFreeMap (© OpenMapTiles, Data from OpenStreetMap)、航空写真は地理院タイル (国土地理院のPDL1.0と個別タイルの条件)。Landsat8・GEBCOと、ズーム2〜8の世界衛星モザイク画像 (NASA/USGS LP DAAC, USGS/EROS) の出典も表示します。GRUS画像（© Axelspace）の配信範囲は対象4都県外の南鳥島です。ブラウザが直接読み、このリポジトリには入れません。

外部データセットの内容には各提供者の条件が引き続き適用されます。生成データベースの ODbL 1.0 は、N02/N03 の CC BY 4.0 や ABR の PDL1.0 を置き換えるものではありません。出典・規約リンク・加工主体を保持して再利用してください。取得元を再確認した記録と、N03 の測量法に関する未確定事項は [docs/data-sources.md](docs/data-sources.md) にあります。
