# fuzzyif 設計書

日付: 2026-09-19
状態: v0.2（批判的レビュー反映済み）

## 1. 目的

Python の `if` 文の条件に、自然言語の問いをそのまま書けるようにする。判定は TypeSafe AI の Jev（System One モデル）に委譲し、Jev が返す確率をしきい値で bool に落とす。

```python
from fuzzyif import fuzzy, fuzzy_match

msg = "ログイン後に画面が真っ白になります"

# 独立した Yes/No 判定
if fuzzy("これは緊急か", msg):
    notify_oncall(msg)

# 排他的な分岐（API 1回で最も近いものを選ぶ）
kind = fuzzy_match(msg, {
    "bug":   "不具合の報告",
    "howto": "使い方の質問",
    "other": "その他",
})
if kind == "bug":
    create_bug_ticket(msg)
elif kind == "howto":
    reply_faq(msg)
else:
    escalate(msg)
```

通常の `if` では書けない「意味に基づく分岐」を、Python の制御構文を変えずに書けるようにするのがゴール。

### fuzzy と fuzzy_match の使い分け（重要）

`fuzzy()` は Jev の noul 型で「この問いに Yes か」を独立に答える。複数の `fuzzy()` を `if / elif` で並べても、各問いは互いを知らないので排他的にならない。実測では「パスワードを変更したいのですができません」に対し「不具合か」0.76、「使い方の質問か」0.89 と両方がしきい値を超え、先に書いた分岐が勝ってしまう。

「どれか1つに分類したい」ときは `fuzzy_match()` を使う。Jev の choice 型で全選択肢を同時に比較し、最も確からしいものを返す。API 呼び出しも1回で済む。

| 用途 | 使う関数 |
|---|---|
| Yes/No を1つ判定 | `fuzzy()` |
| 複数の Yes/No を独立に判定 | `fuzzy_batch()` |
| 選択肢から1つに分類 | `fuzzy_match()` |
| 段階で評価 | `fuzzy_score()` |

## 2. スコープ

### v0.2 に含める

- `fuzzy(question, text, threshold=0.5, default=None) -> bool`
- `prob(question, text, default=None) -> float`
- `fuzzy_batch(text, questions, default=None) -> list[float]`
- `fuzzy_match(text, choices, default=None, with_probs=False) -> str | tuple[str, dict]`
- `fuzzy_score(text, question, levels, default=None) -> float`
- インメモリ LRU キャッシュ
- Jev API クライアント（keep-alive、リトライ、例外変換）
- 設定（API キー探索、タイムアウト、キャッシュサイズ）
- テスト用モック
- 型ヒントと docstring

### 含めない

- 非同期 API
- 永続キャッシュ
- 既存 `if` 文の自動変換ツール（第10章で将来設計だけ書く）
- Jev 以外のバックエンド

## 3. 公開 API

### 3.1 `fuzzy(question, text, *, threshold=0.5, default=None) -> bool`

| 引数 | 型 | 意味 |
|---|---|---|
| `question` | str | Yes/No 質問。「〜か」で終わる形を推奨 |
| `text` | str | 判定対象。空または空白のみなら `ValueError` |
| `threshold` | float | この値以上なら True。0.0〜1.0 の範囲外は `ValueError`。既定 0.5 |
| `default` | bool または None | API 失敗時の戻り値。None なら `APIError` を送出 |

実装: `prob()` を呼び、`APIError` を捕まえて `default` が None でなければそれを返す。それ以外は `prob >= threshold`。

### 3.2 `prob(question, text, *, default=None) -> float`

Jev の noul 型で質問し、確率を返す。`default` は float または None。失敗時に `default` が None でなければそれを返し、None なら `APIError`。

### 3.3 `fuzzy_batch(text, questions, *, default=None) -> list[float]`

複数の Yes/No 質問を1リクエストで投げ、確率のリストを `questions` と同じ順で返す。`default` は float または None で、失敗時は全要素にその値を入れたリストを返す。

キャッシュは質問ごとに個別に保存する。一部がキャッシュにあれば、残りだけをリクエストする。

### 3.4 `fuzzy_match(text, choices, *, default=None, with_probs=False)`

| 引数 | 型 | 意味 |
|---|---|---|
| `text` | str | 判定対象 |
| `choices` | dict[str, str] | キー: 選択肢の識別子、値: その説明。2つ以上必須 |
| `default` | str または None | 失敗時に返すキー。None なら `APIError`。`choices` にないキーは `ValueError` |
| `with_probs` | bool | True なら `(選ばれたキー, {キー: 確率})` のタプルを返す |

Jev の choice 型を使う。`instructions` は「次の選択肢のうち、このテキストに最も当てはまるものはどれか」を固定文で送る。

### 3.5 `fuzzy_score(text, question, levels, *, default=None) -> float`

| 引数 | 型 | 意味 |
|---|---|---|
| `question` | str | 何を測るか（例:「顧客の怒りの度合い」） |
| `levels` | list[str] | 順序のある段階。先頭が 0。2つ以上必須 |
| `default` | float または None | 失敗時の戻り値 |

Jev の score 型を使い、期待値（0〜len(levels)-1 の小数）を返す。

### 3.6 `configure(**kwargs)`

プロセス全体の設定を上書きする。呼び出すとキャッシュを全クリアする。起動時に1回呼ぶ前提で、実行中に繰り返し呼ぶ用途は想定しない。

| キー | 既定値 | 意味 |
|---|---|---|
| `api_key` | 探索順は第6章 | TypeSafe API キー |
| `model` | `"jev-latest"` | モデル名 |
| `timeout` | 10.0 | HTTP タイムアウト秒 |
| `cache_size` | 1024 | LRU のエントリ数。0 で無効 |
| `base_url` | `https://api.typesafe.ai` | エンドポイント |
| `max_retries` | 3 | リトライ回数 |

### 3.7 `mock(mapping=None, *, default_prob=None)`

コンテキストマネージャ。有効中は API を叩かず、キャッシュも読まず書かない。

`mapping` は質問文（`fuzzy_match` なら `choices` のキーをソートして `|` で連結した文字列、`fuzzy_score` なら question）から値への辞書。値は次のいずれか。

- float: テキストに関係なくその確率
- dict[str, float]: テキストから確率への辞書。該当なしなら `default_prob`
- callable: `f(text) -> float`

`fuzzy_match` の mock 値は選ばれるキー（str）またはテキストからキーへの辞書または callable。

該当がなく `default_prob` も None なら `MockMissError`。

```python
with fuzzyif.mock({
    "これは緊急か": {"サーバーが落ちた": 0.95, "来週の会議について": 0.1},
    "bug|howto|other": lambda t: "bug" if "エラー" in t else "howto",
}):
    ...
```

### 3.8 例外

| 例外 | 継承元 | 条件 |
|---|---|---|
| `FuzzyIfError` | Exception | 基底 |
| `ConfigError` | FuzzyIfError | API キー未設定など |
| `APIError` | FuzzyIfError | リトライ後も失敗。`status_code`、`body`、`attempts` 属性を持つ |
| `MockMissError` | FuzzyIfError | mock 中に未定義の質問が来た |

`ValueError` は入力検証（空テキスト、範囲外のしきい値、選択肢1つ以下、`default` が `choices` にない）で送出し、`FuzzyIfError` の下には置かない。呼び出し側のバグなので API 失敗と区別する。

## 4. モジュール構成

```
fuzzyif/
├── __init__.py      # 公開 API の再エクスポート
├── core.py          # fuzzy, prob, fuzzy_batch, fuzzy_match, fuzzy_score, configure
├── client.py        # JevClient: HTTP 呼び出し、keep-alive、リトライ、例外変換
├── cache.py         # スレッドセーフな LRU キャッシュ
├── config.py        # Settings dataclass、API キー探索
├── mock.py          # mock コンテキストマネージャ
└── errors.py        # 例外定義
```

各モジュールの責務は1つ。`core.py` だけが他を束ねる。

### 依存関係

- 実行時: 標準ライブラリのみ（`http.client`、`json`、`threading`、`ssl`）
- 開発時: `pytest`

## 5. データフロー

```
fuzzy(q, t, threshold)
  └→ prob(q, t)
       ├→ 入力検証（t が空なら ValueError）
       ├→ mock 有効?  → mapping から返す（キャッシュは触らない）
       ├→ cache hit?  → キャッシュから返す
       └→ JevClient.ask({q: noul})
            ├→ POST /v1/systemone（keep-alive 接続を再利用）
            ├→ 失敗時はリトライ（第7章）
            ├→ answers[q].noul を float で取り出す
            └→ 例外変換 → APIError
       └→ cache に保存
  └→ prob >= threshold（APIError は default があれば吸収）

fuzzy_match(t, choices)
  └→ 同じ流れで JevClient.ask({"_match": choice})
       └→ answers._match.choice と probabilities を返す

fuzzy_batch(t, [q1..qn])
  └→ キャッシュにない質問だけを1リクエストにまとめる
```

キャッシュのキーは `(kind, model, question_key, text)`。`kind` は `"noul"` / `"choice"` / `"score"`。`question_key` は noul なら質問文、choice なら `choices` を JSON 化した文字列、score なら question と levels を JSON 化した文字列。`threshold` は含めない。

## 6. API キーの探索順

1. `configure(api_key=...)`
2. 環境変数 `TYPESAFE_API_KEY`
3. ファイル `~/.config/typesafe/api_key`（1行目を strip）

いずれもなければ最初の API 呼び出し時に `ConfigError`。import 時には失敗させない。

## 7. HTTP クライアントとリトライ

- `http.client.HTTPSConnection` を1つ保持し、接続を再利用する。接続が切れていたら（`BadStatusLine`、`ConnectionResetError`、`RemoteDisconnected`）1回だけ再接続して再送する。これはリトライ回数に数えない。
- リトライ対象: HTTP 429、5xx、タイムアウト、接続失敗。4xx（429 以外）は即 `APIError`。
- バックオフ: 0.5秒、1秒、2秒（`max_retries=3` のとき）。429 で `Retry-After` ヘッダがあればそれに従う。
- 全リトライ失敗で `APIError`。`attempts` に試行回数を入れる。
- クライアントはスレッドごとに接続を持つ（`threading.local`）。プロセス間では共有しない。

## 8. エラー処理の方針

- API 失敗時、`default` が None でなければそれを返し、`logging.getLogger("fuzzyif")` に WARNING を出す。
- `default` が None なら `APIError` を送出する。if 文の中で黙って False になるのは危険なので、既定は例外。
- 否定形 `if not fuzzy(...)` で `default=False` を使うと、障害時に全件が True 側に流れる。ドキュメントで注意を書く。
- レスポンスに期待するフィールドがない、または型が違うときは `APIError`。
- 入力検証エラーは `ValueError`。

## 9. テスト戦略

- `client.py`: `http.client.HTTPSConnection` を差し替えて、正常、4xx、429（Retry-After あり/なし）、5xx、タイムアウト、接続切れからの再接続、不正 JSON。
- `cache.py`: LRU の追い出し順、サイズ0、スレッドから同時アクセス、`configure()` でクリア。
- `core.py`: threshold 境界（ちょうど 0.5 は True）、空テキスト、`default` の型ごとの挙動、`fuzzy_match` の `with_probs`、`fuzzy_batch` の部分キャッシュヒット。
- `mock.py`: float / dict / callable の3形式、`MockMissError`、mock 中にキャッシュへ書かれないこと。
- `config.py`: キーの探索順。
- 実 API を叩く統合テストは `TYPESAFE_API_KEY` があるときだけ実行。

## 10. 将来: if 文の自動変換ツール（fuzzyif-convert）

v0.2 には含めない。

### 何をするか

既存の Python ソースから「テキストに対する条件分岐」を見つけ、`fuzzy()` / `fuzzy_match()` 呼び出しに書き換える提案を出す。書き換えは人が承認してから適用する。

```python
# 変換前
if "エラー" in msg or "動かない" in msg:
    create_bug_ticket(msg)
elif "使い方" in msg or "どうやって" in msg:
    reply_faq(msg)

# 変換後（提案）
kind = fuzzy_match(msg, {"bug": "不具合の報告", "howto": "使い方の質問", "other": "その他"})
if kind == "bug":
    create_bug_ticket(msg)
elif kind == "howto":
    reply_faq(msg)
```

### どう動くか

1. `ast` でソースを解析し、`if` / `elif` チェーンを列挙する。
2. 条件式が「同じ変数に対する `in`、`startswith`、`re.search`、`==` の組み合わせ」なら変換候補にする。
3. 候補ごとに、条件式と前後のコードを LLM（Claude）に渡して「この条件が意図している自然言語の問い」を生成させる。チェーン全体が同じ変数を見ているなら `fuzzy_match()` に、単独なら `fuzzy()` に変換する。
4. diff を出力する。
5. 変換前後で同じテストデータを流し、判定の一致率を報告する。

### 未解決の論点

- 変数が文字列かどうかは静的に分からない。型ヒントがあるものだけ対象にするか、実行時トレースを使うか。
- `"エラー" in msg` を「不具合か」に変換すると、元コードが除外していたケース（「エラー」を含まない不具合報告）を含める意味の拡張になる。一致率が下がったときに変換を提案しない、という方針にするか。
- 問いの生成に使う LLM とプロンプト。
- `or` で繋がった条件を1つの問いにまとめるか、複数の `fuzzy()` の `or` にするか。

## 11. 判断の記録

| 論点 | 決定 | 理由 |
|---|---|---|
| 条件の形 | 自然言語の質問 | ユーザー選択 |
| しきい値 | 既定 0.5、引数で上書き | ユーザー選択 |
| 排他分岐 | `fuzzy_match()` を入れる | レビュー指摘1。noul の if/elif は排他にならないことを実証 |
| 複数判定 | `fuzzy_batch()` を入れる | レビュー指摘2。個別呼び出しは 2.4 倍の時間、2.6 倍のトークン |
| キャッシュキー | model を含め、configure() でクリア | レビュー指摘3 |
| HTTP | 標準ライブラリで keep-alive とリトライ | レビュー指摘4。接続確立が1回の56% |
| mock の値 | float / dict / callable | レビュー指摘5 |
| mock とキャッシュ | mock 中はキャッシュを触らない | レビュー指摘6 |
| default の型 | prob は float、fuzzy は bool | レビュー指摘7 |
| 空テキスト | ValueError | レビュー指摘8。API は空でも 200 を返す |
| スレッド安全 | キャッシュに Lock、接続は threading.local | レビュー指摘9 |
| API 失敗時 | 既定は例外 | レビューで覆す根拠なし |
| 変換ツール | 設計のみ、未解決論点を追記 | レビュー指摘10 |

## 12. 批判的レビューの記録（2026-09-19）

subagent による敵対的検証。実 API を約15回叩いて実証。判定「重大な課題あり」。Major 4件と Minor 6件をすべて v0.2 に反映した。

検証したが成立しなかった仮説:

- 非決定性: 同一リクエスト3回で 0.95 が3回一致
- 既定を例外にする判断: 例外にも default=False にも破綻シナリオがあり、覆す根拠なし
- しきい値 0.5: 境界付近のケースは実在するが、どの固定値でも境界はある
- TLS 検証・プロキシ: `http.client` の既定で足りる
