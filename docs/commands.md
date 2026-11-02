# Codexが使うコマンド

ユーザーはCodexへ自然言語で依頼する。以下はCodexが実行するための参照。

実行形式は、セットアップで作ったPythonを使った `<python> scripts/studio.py <command>`。作業ディレクトリを変える必要はなく、スクリプトと作品の絶対パスでも実行できる。各コマンドの引数は `--help` で確認できる。

| コマンド | 用途と主な引数 |
|---|---|
| `doctor` | OS・Python・VectorCraft設定を確認 |
| `setup` | `--vectorcraft` で既存実行ファイルを指定。不足時は公式配布物を取得。`--from-source` でソースから準備 |
| `new` | `--project` `--name` `--phrases` で作品を初期化。セリフはUTF-8のJSON配列 |
| `reference-add` | `--project` `--file` で原本を保持した参照コピーを登録 |
| `artwork-add` | `--project` `--id` `--file` で原画を版ごとに保存 |
| `launch` | `--project` で専用のVectorCraftを起動。`--vectorcraft` と `--port` は任意指定 |
| `native` | `--project` `--method` `--params` でネイティブAPIを呼ぶ。引数はJSONファイル |
| `screenshot` | `--project` と任意の `--file` でGUIをPNGへ保存 |
| `native-register` | `--project` `--id` `--file` で編集ファイルを制作記録へ登録 |
| `review-open` | `--project` `--ids 01 02 ...` で個別タブを開く |
| `review-complete` | `--project` `--ids` `--human-message` で保存と人間の確認記録 |
| `export` | `--project` `--ids` で確認済みソースから最終PNGと明暗の確認画像を出力 |
| `visual-record` | `--project` `--ids` `--note` `--backgrounds light dark` で実際の目視所見を記録 |
| `spec-confirm` | `--project` で公式仕様の確認日を記録。先に公式ページと検査条件を照合する |
| `tags` | `--project` で設定済みの検索語候補をテキストへ出力 |
| `verify` | `--project` で技術条件・原本・レビュー・出力・目視記録の対応を確認 |
| `package` | `--project` で検証後にZIP、タグ用テキスト、検証記録を作成 |
| `status` | `--project` で作品の進行記録を表示 |

## 設定する内容

`project.json` はCodexがユーザーとの合意を反映して編集する。

- `character`：維持する外見、衣装、左右関係、口調、設定の参照元。
- `design_direction`：構図、縦横比、重なり、書体や配色の考え方、合意した判断基準。
- `items`：各セリフの `emotion`、`pose`、`composition`、タグ検索候補 `tags`。
- `title` と `description`：言語ごとの文面と確定状況。未確定を確定と扱わない。
- `review_batch_size`：一度に確認する点数。
- `image_generation.availability_checked`：現在のCodexで画像生成ツールを確認した結果。

IDは `01` から連続する番号と `main`、`tab`。順序と件数を変える場合は、既存画像・承認との対応を再確認する。

`state.json` はコマンドが更新する。レビュー、出力、目視所見のハッシュを手作業で書き換えて検証を通さない。

## Pythonからの操作

作品固有の制作スクリプトは作品の `production/` に保存する。リポジトリの `src/` をPythonの検索先へ加え、`sticker_studio.vectorcraft.Client` を使える。

同じ作品のネイティブ操作をスクリプトでまとめる場合は `sticker_studio.project.lock` の中で実行する。制作スクリプトにも開始・終了・エラーを記録する。

スクリプトの座標、フォント、配色は画像ごとに設計する。コマンド例の既定値をその案件の決定事項として流用しない。
