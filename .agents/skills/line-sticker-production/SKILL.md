---
name: line-sticker-production
description: Create and revise editable ordinary static LINE sticker sets from character references in this repository, including VectorCraft setup, text-free artwork, lettering, human review, PNG validation and upload ZIP preparation. Use for starting or resuming static sticker production in this project. Documentation edits do not require launching VectorCraft.
---

# LINEスタンプ制作

ユーザーの参照画像を基に、文字なし原画、編集可能なVectorCraftファイル、最終PNG、Main・Tab、タグ検索候補、アップロード用ZIPを制作する。

## 開始と再開

1. 初回は [README](../../../README.md) と [セットアップ](../../../docs/setup.md) を読む。Codexの画像生成ツールが利用できるか、現在のツール一覧で確認する。
2. 利用可能なPython 3.11以上を選び、`scripts/bootstrap.py` を実行する。既存VectorCraftがあれば `--vectorcraft` で再利用する。ユーザーにコマンドの入力を任せない。
3. 作品が既にあれば `project.json`、`state.json`、実ファイルを確認して続きから進める。セットアップ済み環境や参照画像を作り直さない。
4. 新規作品では `input/references/` またはユーザー指定のパスから参照画像を確認し、用途、口調、枚数、セリフ、名前表記、デザイン条件を相談する。不明な内容を確定情報として埋めない。
5. 合意したセリフのJSON配列を用意し、`new` で `projects/<作品名>/` を初期化する。参照画像は `reference-add` で原本を保持したコピーとして登録する。

## 制作

詳細は [制作フロー](../../../docs/workflow.md)、ネイティブ操作は [VectorCraftの操作](../../../docs/vectorcraft.md)、各コマンドは [コマンド一覧](../../../docs/commands.md) を必要な段階で読む。本文中のコマンド・保存先はリポジトリルートを基準とする。

1. 参照画像と設定を目視し、維持する外見と左右関係を `project.json` に記録する。
2. 各画像について、セリフ、単一の感情、表情、ポーズ、構図を設計する。質問の疑問符や感嘆符も確定する。
3. Codexの画像生成ツールを使い、参照画像に基づく文字なし・背景透過の原画を生成する。文字や後から編集する装飾を焼き込まない。生成物は `artwork-add` で作品内へ保存する。
4. 原画を参照画像と照合し、外見、衣装、左右、手指、見切れ、透過、不要な文字を目視確認する。問題があれば修正してから進む。
5. VectorCraftを起動し、GUIと制御接続を確認する。原画、文字、装飾を編集可能な状態で構成し、1点につき1ファイルに保存する。未確定の方針は代表サンプルで人間に確認する。
6. サンプルで合意した判断基準を使い、残りのデザインを個別に制作する。フォント、配色、文字位置、重なり方を一律に固定しない。
7. 合意した単位で個別タブを開いて人間の確認を受ける。ユーザーの完了報告を受けて変更を保存し、`review-complete` に実際の発言を記録する。勝手に次の確認単位へ進めない。
8. Main・Tabも用途に合う構図で別途制作し、人間の確認対象に含める。文字の有無やトリミングは案件ごとに決める。

## 出力と完了

1. 現行のLINE公式仕様を開いて確認し、実装済みの検査条件とも突き合わせた後に `spec-confirm` を実行する。仕様が変わっていたら、記録だけ更新して済ませず検査条件を直す。
2. 人間が確認した最新版から `export` でPNGと明暗の確認画像を出力する。サイズ、容量、透過、余白、解像度、フォントの問題を解消する。
3. 明暗両背景と実寸で全画像を目視する。確認したPNGに対してのみ `visual-record` で所見を残す。出力やソースが変わったら再確認する。
4. 各セリフに合うタグ検索候補を用意する。実画面の候補一覧との一致が未確認なら、その状態を明記する。
5. `verify` と `package` を実行し、PNGだけを格納したZIP、タグ用テキスト、検証記録を作る。
6. 保存先、確認範囲、未確定事項を報告し、[LINEへの登録ガイド](../../../docs/registration.md)とブラウザで読める[HTML版](../../../docs/registration.html)を案内する。実際のLINEへのアップロードや審査申請は、今回のユーザーの依頼範囲を確認して扱う。

並列化する場合は同じ工程内に限定する。同じVectorCraftインスタンスへの編集はアクティブ文書を確認しながら順次実行する。
