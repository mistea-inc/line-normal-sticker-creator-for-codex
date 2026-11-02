# セットアップ

この手順はCodexが実行する。ユーザーには環境の選択や必要な認証を依頼し、通常のコマンド入力は任せない。

## 初回確認

OS、CPU、Python、デスクトップ表示、画像生成ツールの有無を確認する。Pythonは3.11以上を選ぶ。利用可能な `python3`、`python`、WindowsのPython Launcher、または既に導入された `uv` の管理環境を使う。

Pythonが無い場合は、そのOSの公式導入手順と実行権限を確認して対応する。存在しないPythonでブートストラップできるとは報告しない。

画像生成ツールは現在のCodexのツール一覧から確認する。`doctor` が出す文面は利用可能性の判定ではない。ツールが無ければ、ユーザーのCodex環境で利用可能にするための確認へ進む。

## Python環境

リポジトリ直下の `scripts/bootstrap.py` を選んだPythonで実行する。`.venv` を作り、検証用のPillowをインストールした後、VectorCraftを準備する。

既存のVectorCraftを再利用する場合は `--vectorcraft <実行ファイル>` を渡す。Python環境だけ準備する場合は `--skip-tools` を渡す。

以降のコマンドは `.venv` のPythonで `scripts/studio.py` を実行する。実行ファイルはWindowsでは `.venv/Scripts/python.exe`、macOS・Linuxでは `.venv/bin/python` にある。

## VectorCraft

参照元は [storytold/vectorcraft](https://github.com/storytold/vectorcraft)。取得対象は0.19.0に固定している。

`setup` は明示された実行ファイル、`VECTORCRAFT_BIN`、PATH、前回の設定の順に探し、不足時は公式配布物を取得する。既存ファイルは、後述の起動・描画確認が済むまで動作確認済みと扱わない。

| OS | 取得形式 |
|---|---|
| Windows x64・ARM64 | Portable ZIP |
| macOS Intel・Apple silicon | Universal DMG |
| Linux x86_64・ARM64 | tar.gz |

取得物は公式の `SHA256SUMS.txt` と照合してから展開する。OS全体へインストールせず、利用者用の道具フォルダへ配置する。既定はホーム配下の `ai-base/tools/line-sticker-studio`。`--tools-dir` または `LINE_STICKER_TOOLS_DIR` で変更できる。

ソースから準備する場合は `setup --from-source` を使う。Git、Cargo、コンパイラ、OS別のビルド依存が必要。固定したタグを取得し、公式のビルド方法に沿って実行する。依存が不足している場合は [上流の開発文書](https://github.com/storytold/vectorcraft/blob/main/docs/development.md) で確認して解消する。既存のチェックアウトを削除・初期化しない。

## 起動確認

作品を初期化した後、`launch --project <作品フォルダ>` を実行する。作品ごとに制御ポートと専用プロファイルを記録する。制御チャネルの読み書き先は作品フォルダへ限定する。

1. 制御接続が応答することを確認する。
2. `screenshot` でGUIの描画を確認する。
3. 制作用とは分けた確認文書で、簡単な図形を保存・再オープン・PNG出力する。VectorCraftのネイティブ操作を使い、元の作品ファイルを上書きしない。
4. 使用予定のフォントが読み込まれ、日本語に欠落や代替がないか確認する。
5. ユーザーが編集できるウィンドウを表示する。

WSL2ではLinuxのプロセスとWindows側の表示を分けて確認する。`launch` はWSLを検出した場合にXWayland経由で開く。表示やGPUの問題はプロセスログで確認する。macOSやWindowsのOS側で許可が必要な場合は、通常の認証・許可の操作をユーザーに依頼する。

Linuxの最小構成では、配布物を展開できても `libxkbcommon-x11.so` などの共有ライブラリ不足で起動できない場合がある。`doctor` の結果とプロセスログを確認し、OSのパッケージまたは既存の起動ラッパーで依存を解消する。Ubuntuでは `libxkbcommon-x11-0` など、診断結果に対応するパッケージを確認する。システムを変更できない環境では、ユーザー用に準備済みのライブラリを設定するラッパーを `--vectorcraft` に指定できる。

アプリを閉じた後は `launch` で再開する。接続拒否を受けて作品を再生成したり、ユーザーの設定を削除したりしない。
