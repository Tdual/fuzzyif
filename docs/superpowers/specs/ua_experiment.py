"""python-user-agents のテストケースを Jev で判定し、一致率を測る。"""
import json, re, subprocess, sys, time

SRC = "python-user-agents/user_agents/tests.py"
src = open(SRC, encoding="utf-8").read()

# UA 文字列
uas = dict(re.findall(r"^(\w+)_ua_string = '(.*)'$", src, re.M))

# 期待値: assertTrue/False(xxx_ua.is_yyy)
expected = {}  # (name, prop) -> bool
for m in re.finditer(r"assert(True|False)\((\w+)_ua\.(is_\w+)\)", src):
    expected[(m.group(2), m.group(3))] = m.group(1) == "True"

props = ["is_mobile", "is_tablet", "is_pc", "is_bot"]
names = sorted({n for n, _ in expected if n in uas})

def jev(req):
    out = subprocess.run(["/Users/tdual/bin/jev", "-"], input=json.dumps(req), capture_output=True, text=True)
    return json.loads(out.stdout)

# 1 UA につき choice 1回で4分類
results = {}
t0 = time.time()
for n in names:
    req = {
        "state": uas[n],
        "model": "jev-latest",
        "questions": {
            "kind": {
                "type": "choice",
                "instructions": "この User-Agent 文字列はどの種類のクライアントか",
                "criteria": {
                    "mobile": "スマートフォンや携帯電話（画面の小さい手持ち端末）",
                    "tablet": "タブレット端末（iPad、Android タブレット、Kindle Fire、PlayBook、Windows RT など）",
                    "pc": "デスクトップまたはノートPC（Windows、Mac、Linux、ChromeOS のブラウザ）",
                    "bot": "検索エンジンのクローラーやボット",
                },
            }
        },
    }
    r = jev(req)["answers"]["kind"]
    results[n] = (r["choice"], r["probabilities"])
elapsed = time.time() - t0

# 比較
ok = ng = 0
rows = []
for (n, prop), exp in sorted(expected.items()):
    if n not in results or prop not in props:
        continue
    kind = results[n][0]
    got = {"is_mobile": kind == "mobile", "is_tablet": kind == "tablet", "is_pc": kind == "pc", "is_bot": kind == "bot"}[prop]
    mark = "OK" if got == exp else "NG"
    if got == exp: ok += 1
    else: ng += 1
    rows.append((mark, n, prop, exp, got, kind, results[n][1]))

for r in rows:
    if r[0] == "NG":
        print("NG", r[1], r[2], "expected", r[3], "got", r[4], "| jev:", r[5], {k: round(v, 2) for k, v in r[6].items()})
print(f"\n一致 {ok} / {ok+ng} ({ok/(ok+ng)*100:.1f}%)  UA数 {len(names)}  API呼び出し {len(names)} 回  {elapsed:.1f}秒")
print("\n各UAの判定:")
for n in names:
    print(f"  {n:28s} {results[n][0]:7s}", {k: round(v, 2) for k, v in results[n][1].items()})
