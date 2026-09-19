# fuzzyif 設計書

日付: 2026-09-19
状態: ドラフト（批判的レビュー前）

## 1. 目的

Python の `if` 文の条件に、自然言語の問いをそのまま書けるようにする。判定は TypeSafe AI の Jev（System One モデル）に委譲し、Jev が返す確率をしきい値で bool に落とす。

```python
from fuzzyif import fuzzy

msg = "ログイン後に画面が真っ白になります"

if fuzzy("これは不具合の報告か", msg):
    create_bug_ticket(msg)
elif fuzzy("これは使い方の質問か", msg):
    reply_faq(msg)
else:
    escalate(msg)
```

通常の `if` では書けない「意味に基づく分岐」を、Python の制御構文を変えずに書けるようにするのがゴール。

## 2. スコープ

### 初版（v0.1）に含める

- `fuzzy(question, text, threshold=0.5) -> bool`
- `prob(question, text) -> float`（確率そのものが欲しいとき）
- インメモリキャッシュ（同じ質問・テキストの組で API を叩き直さない）
- Jev API クライアント（HTTP、認証、エラー変換）
- 設定（APIキーの読み込み順、タイムアウト、キャッシュサイズ）
- テスト用のモック機構（API を叩かずに固定値を返す）
- 型ヒントと docstring

### 初版に含めない

- `fuzzy_match()` のような choice 型を使う分岐構文
- 非同期 API（`async def`）
- 永続キャッシュ（ディスク、Redis）
- 既存 `if` 文の自動変換ツール（第9章で将来設計だけ書く）
- Jev 以外のバックエンド

YAGNI で削る。必要になったら足す。

## 3. 公開 API

### 3.1 `fuzzy(question, text, *, threshold=0.5, default=None) -> bool`

| 引数 | 型 | 意味 |
|---|---|---|
| `question` | str | 自然言語の Yes/No 質問。「〜か」で終わる形を推奨 |
| `text` | str | 判定対象のテキスト |
| `threshold` | float | この値以上なら True。0.0〜1.0。既定 0.5 |
| `default` | bool または None | API 失敗時の戻り値。None なら例外を送出 |

戻り値: `prob(question, text) >= threshold`。

### 3.2 `prob(question, text, *, default=None) -> float`

Jev の `noul` 型で質問し、確率を返す。`fuzzy()` はこの関数の薄いラッパー。

### 3.3 `configure(**kwargs)`

プロセス全体の設定を上書きする。

| キー | 既定値 | 意味 |
|---|---|---|
| `api_key` | 後述の探索順 | TypeSafe API キー |
| `model` | `"jev-latest"` | モデル名 |
| `timeout` | 10.0 | HTTP タイムアウト秒 |
| `cache_size` | 1024 | LRU キャッシュのエントリ数。0 で無効 |
| `base_url` | `https://api.typesafe.ai` | エンドポイント |

### 3.4 `mock(mapping=None, *, default_prob=None)`

コンテキストマネージャ。テストで API を叩かずに固定確率を返す。

```python
with fuzzyif.mock({"これは不具合の報告か": 0.9}):
    assert fuzzy("これは不具合の報告か", "anything")
```

`mapping` は質問文から確率への辞書。該当がなく `default_prob` も None なら `MockMissError` を送出する（テストの取りこぼしを防ぐ）。

### 3.5 例外

| 例外 | 継承元 | 条件 |
|---|---|---|
| `FuzzyIfError` | Exception | 基底 |
| `ConfigError` | FuzzyIfError | API キー未設定など |
| `APIError` | FuzzyIfError | HTTP 4xx/5xx、タイムアウト、接続失敗。`status_code` と `body` 属性を持つ |
| `MockMissError` | FuzzyIfError | mock 中に未定義の質問が来た |

## 4. モジュール構成

```
fuzzyif/
├── __init__.py      # 公開 API の再エクスポート
├── core.py          # fuzzy, prob, configure
├── client.py        # JevClient: HTTP 呼び出しと例外変換
├── cache.py         # LRU キャッシュ（functools.lru_cache は使わない。configure で動的にサイズ変更するため）
├── config.py        # Settings dataclass、APIキー探索
├── mock.py          # mock コンテキストマネージャ
└── errors.py        # 例外定義
```

各モジュールの責務は1つ。`core.py` だけが他を束ねる。

### 依存関係

- 実行時依存: なし（標準ライブラリの `urllib.request` と `json` のみ）。`requests` や `httpx` を要求しない。
- 開発時依存: `pytest`

理由: 「if 文の代わり」に使うモジュールが重い依存を持つと導入の敷居が上がる。Jev の API は単純な POST 1本なので標準ライブラリで足りる。

## 5. データフロー

```
fuzzy(q, t, threshold)
  └→ prob(q, t)
       ├→ mock 有効?  → mapping から返す
       ├→ cache hit?  → キャッシュから返す
       └→ JevClient.noul(q, t)
            ├→ POST /v1/systemone  {"state": t, "model": m, "questions": {"q": {"type":"noul","instructions": q}}}
            ├→ レスポンス answers.q.noul を float で取り出す
            └→ 例外変換（urllib.error → APIError）
       └→ cache に保存
  └→ prob >= threshold
```

キャッシュのキーは `(question, text)` のタプル。`threshold` はキーに含めない。同じ確率に別のしきい値を当てるときは API を叩き直さない。

## 6. API キーの探索順

1. `configure(api_key=...)` で明示されたもの
2. 環境変数 `TYPESAFE_API_KEY`
3. ファイル `~/.config/typesafe/api_key`（1行目を strip）

いずれもなければ最初の `prob()` 呼び出し時に `ConfigError`。import 時には失敗させない（テストや静的解析で import だけしたいケースがあるため）。

## 7. エラー処理の方針

- API 失敗時、`default` が与えられていればそれを返す。ログに WARNING を出す（`logging.getLogger("fuzzyif")`）。
- `default` が None なら `APIError` を送出する。if 文の中で黙って False になるのは危険なので、既定は例外。
- Jev のレスポンスに `answers[q].noul` がない、または float に変換できないときは `APIError` として扱う。
- `threshold` が 0〜1 の範囲外なら `ValueError`（設定ミスは早く落とす）。

## 8. テスト戦略

- `client.py`: `urllib.request.urlopen` を monkeypatch して、正常レスポンス、4xx、5xx、タイムアウト、不正JSON の5系統。
- `cache.py`: LRU の追い出し順、サイズ0で無効化。
- `core.py`: threshold の境界値（ちょうど0.5 は True）、default の挙動、mock との組み合わせ。
- `config.py`: キーの探索順。環境変数とファイルの両方があるとき環境変数が勝つ。
- 実 API を叩く統合テストは `TYPESAFE_API_KEY` があるときだけ実行（`pytest.mark.skipif`）。

## 9. 将来: if 文の自動変換ツール（fuzzyif-convert）

初版には含めないが、モジュール設計はこれを見越している。

### 何をするか

既存の Python ソースから「テキストに対する条件分岐」を見つけ、`fuzzy()` 呼び出しに書き換える提案を出す。

```python
# 変換前
if "エラー" in msg or "動かない" in msg or "できない" in msg:
    create_bug_ticket(msg)

# 変換後（提案）
if fuzzy("これは不具合の報告か", msg):
    create_bug_ticket(msg)
```

### どう動くか

1. `ast` でソースを解析し、`if` / `elif` の条件式を列挙する。
2. 条件式が「文字列変数に対する `in`、`startswith`、`re.search`、`==` の組み合わせ」なら変換候補にする。数値比較や None チェックは対象外。
3. 候補ごとに、条件式と前後のコード（関数名、コメント、分岐先の処理）を LLM（Claude）に渡して「この条件が意図している自然言語の問い」を生成させる。
4. `fuzzy(<生成した問い>, <変数名>)` に置き換えた diff を出力する。書き換えは人が承認してから適用する（自動適用しない）。
5. 変換前後で同じテストデータを流し、判定の一致率を報告する。

### 初版のモジュール設計が効く点

- `fuzzy()` の第1引数が質問文、第2引数がテキスト、という単純な形にしてあるので、AST での書き換えが機械的にできる。
- `mock()` があるので、変換後のコードのテストが API なしで書ける。
- `prob()` があるので、一致率レポートでしきい値の調整ができる。

### 未解決の論点（変換ツール着手時に決める）

- 変換対象にする条件式のパターンをどこまで広げるか
- 問いの生成に使う LLM とプロンプト
- `or` で繋がった条件を1つの問いにまとめるか、複数の `fuzzy()` の `or` にするか

## 10. 判断の記録

| 論点 | 決定 | 理由 |
|---|---|---|
| 条件の形 | 自然言語の質問 | ユーザー選択。通常の if で書けない判定を可能にするのが目的 |
| しきい値 | 既定 0.5、引数で上書き | ユーザー選択。単純で予測しやすい |
| API 呼び出し | 1判定1呼び出し + キャッシュ | ユーザー選択。実装が単純で、elif は必要なときしか評価されないので無駄が少ない |
| API 失敗時 | 既定は例外、`default` で抑制 | if の中で黙って False になると気づけない |
| HTTP ライブラリ | 標準ライブラリ | 依存ゼロで導入しやすくする |
| 非同期 | 初版では非対応 | 需要が見えてから |
| 変換ツール | 初版では設計のみ | モジュールの API を固めてから着手する |

## 11. 批判的レビューの結果と対応案（2026-09-19）

subagent による敵対的検証。実 API を約15回叩いて実証済み。判定は「重大な課題あり」（確度高の Major 3件、確度中の Major 1件）。採否は未決定。

| # | 指摘 | 深刻度 | 確度 | 対応案 |
|---|---|---|---|---|
| 1 | if/elif は独立した noul の順次判定なので、複数が同時に threshold を超えると「先に書いた分岐」が勝ち、最も確からしい分岐にならない。実測: 「パスワードを変更したいのですができません」で bug=0.76, faq=0.89 | Major | 高 | `fuzzy_match()`（choice 型）を初版に含める。ドキュメントで「排他分岐は fuzzy_match、独立判定は fuzzy」と使い分けを明記 |
| 2 | else 到達時は N 回直列呼び出し。実測: 3質問を個別に叩くと 2.42秒 / 884 tokens、1回にまとめると 0.97秒 / 332 tokens | Major | 高 | 対応案1で排他分岐が1回になれば大半は解消。独立判定を複数並べる場合向けに `fuzzy_batch(text, [q1, q2, ...]) -> list[float]` を追加 |
| 3 | キャッシュキーが (question, text) のみで model / base_url を含まない。configure() 後も旧値が返る | Major | 中 | configure() 呼び出し時にキャッシュを全クリア。キーに model を含める |
| 4 | urllib.request は接続を再利用せず、1呼び出しの56%が TCP+TLS 確立。リトライ方針も未記述 | Major | 高 | http.client.HTTPSConnection を保持して keep-alive。5xx/429/接続失敗は指数バックオフで最大3回リトライ。標準ライブラリのみは維持 |
| 5 | mock の mapping が質問文のみをキーにし text を無視するため、elif の2番目以降や else に落ちるテストが1ブロックで書けない | Minor | 中 | mapping の値に「確率」または「text -> 確率 の辞書」または「callable(text) -> 確率」を許す |
| 6 | mock の結果がキャッシュに残るか、mock 中にキャッシュが先に返るかが未定義 | Minor | 中 | mock 有効中はキャッシュを読まず書かない、と明記 |
| 7 | prob() の default の型が未定義。fuzzy() が bool の default を prob() に渡す実装になりうる | Minor | 中 | prob(default: float or None)、fuzzy(default: bool or None) と分け、fuzzy は prob の APIError を捕まえて default を返す |
| 8 | text="" でも API は 200 と確率（0.37）を返す。空のまま分岐に到達しても気づけない | Minor | 高 | text が空または空白のみなら ValueError |
| 9 | configure() のグローバル状態とキャッシュのスレッド安全性が未記述 | Minor | 低 | キャッシュに threading.Lock。configure() は起動時に1回呼ぶ前提と明記 |
| 10 | 第9章の AST 検出は変数の型が静的に分からず、「"エラー" in msg」→「不具合か」の変換は元コードが除外していたケースを含める意味拡張になる | Minor | 低 | 第9章の未解決論点に追加。変換は「提案」止まりで人が承認、という方針は維持 |

### 検証したが成立しなかった仮説

- 非決定性: 同一リクエスト3回で noul=0.95 が3回一致。出力は安定
- 既定 default=None（例外）: 例外にも default=False にも破綻シナリオがあり、覆す根拠なし
- threshold=0.5: 境界付近のケース（0.52）は実在したが、どの固定値でも境界は存在する。指摘1が本質
- TLS 検証・プロキシ: urllib.request の既定で足りる
