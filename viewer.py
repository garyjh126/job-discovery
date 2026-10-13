"""Build data/roles.html: every matching role from the latest sweep, sorted by priority to apply.

Usage: python3 -I viewer.py            (normally called by daily.py after each sweep)

Priority = Claude's fit score from data/scores.json when there is one, otherwise a rough
keyword match (title, contract/remote, location, freshness). Open data/roles.html in a browser.

data/scores.json (kept by Claude when it scores roles; optional):
  {"<posting url>": {"score": 6.5, "note": "one line", "status": "applied"}}
"""
import datetime, glob, html, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

ATS_NAME = {"gh": "Greenhouse", "lever": "Lever", "ashby": "Ashby", "workable": "Workable",
            "recruitee": "Recruitee", "personio": "Personio"}
WEIGHTS = [  # (pattern, points) on the title
    (r"reinforcement|\brl\b|game|multi.agent|simulation|optimi[sz]", 3),
    (r"c\+\+|low.latency|quant|research engineer|performance", 2),
    (r"machine learning|\bml\b|\bmle\b|inference|\bgpu\b|ai engineer|applied scientist", 2),
    (r"backend|back-end|platform", 1),
    (r"\bsenior\b|\bsr\.?\b", 1),
]
CONTRACT = re.compile(r"contract|freelance|temporary|fixed.term", re.I)
REMOTE = re.compile(r"remote|anywhere", re.I)
HOME = re.compile(r"ireland|dublin|cork|united kingdom|\buk\b|london|europe|emea|georgia|tbilisi", re.I)
ELSEWHERE = re.compile(r"\busa?\b|united states|canada|india|brazil|latam|mexico|apac|singapore|japan|australia", re.I)
ANYWHERE = re.compile(r"anywhere|worldwide|global", re.I)


def rough(h, today):
    t = h["title"]
    pts = sum(p for pat, p in WEIGHTS if re.search(pat, t, re.I))
    if CONTRACT.search(h.get("type") or "") or CONTRACT.search(t):
        pts += 3
    loc = h.get("location") or ""
    if REMOTE.search(loc) and (HOME.search(loc) or ANYWHERE.search(loc) or not ELSEWHERE.search(loc)):
        pts += 2  # remote that plausibly includes the HOME regions; "Remote - USA/India" earns nothing
    if HOME.search(loc):
        pts += 1
    try:
        if (today - datetime.date.fromisoformat(h["date"])).days <= 7:
            pts += 1
    except ValueError:
        pass
    return pts


def boards():
    out = {}
    for line in open(os.path.join(DATA, "companies.txt")):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        out[parts[2] if len(parts) > 2 else parts[1]] = ATS_NAME.get(parts[0], parts[0])
    return out


def build():
    runs = sorted(glob.glob(os.path.join(DATA, "runs", "*.json")))
    if not runs:
        return None
    run_date = os.path.basename(runs[-1])[:-5]
    run = json.load(open(runs[-1]))
    seen = json.load(open(os.path.join(DATA, "seen.json"))) if os.path.exists(os.path.join(DATA, "seen.json")) else {}
    scores_file = os.path.join(DATA, "scores.json")
    scores = json.load(open(scores_file)) if os.path.exists(scores_file) else {}
    ats = boards()
    today = datetime.date.fromisoformat(run_date)

    rows = []
    for company, r in run["results"].items():
        for h in r["hits"]:
            s = scores.get(h["url"], {})
            rows.append(dict(company=company, title=h["title"], url=h["url"], location=h["location"] or "",
                             type=h.get("type") or "", posted=h.get("date") or "", first_seen=seen.get(h["url"], ""),
                             source=ats.get(company, ""), rough=rough(h, today),
                             score=s.get("score"), note=s.get("note", ""), status=s.get("status", "")))
    rows.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0), -x["rough"], x["company"].lower()))

    board_rows = [dict(company=c, source=ats.get(c, ""), total=r["total"], hits=len(r["hits"]), ok=True)
                  for c, r in run["results"].items()]
    board_rows += [dict(company=c, source=ats.get(c, ""), total=0, hits=0, ok=False) for c in run["missing"]]
    board_rows.sort(key=lambda b: (b["ok"], b["company"].lower()))

    page = TEMPLATE.replace("__DATA__", json.dumps(dict(
        run_date=run_date, rows=rows, boards=board_rows,
        n_ok=len(run["results"]), n_missing=len(run["missing"]))).replace("</", "<\\/"))
    out = os.path.join(DATA, "roles.html")
    open(out, "w").write(page)
    return out


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Open roles</title>
<style>
:root{--bg:#fafaf9;--fg:#1c1917;--muted:#78716c;--line:#e7e5e4;--card:#fff;--accent:#2563eb;--warn:#b45309;--warnbg:#fef3c7;--good:#15803d}
@media (prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--muted:#a8a29e;--line:#44403c;--card:#292524;--accent:#60a5fa;--warn:#fbbf24;--warnbg:#422006;--good:#4ade80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,system-ui,sans-serif}
main{max-width:1200px;margin:0 auto;padding:20px 16px}h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px}
.sub{color:var(--muted);margin:0 0 16px}.warn{background:var(--warnbg);color:var(--warn);padding:8px 12px;border-radius:6px;margin:0 0 16px}
.bar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:0 0 12px}input[type=search]{flex:1;min-width:200px;padding:7px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)}
label{color:var(--muted);white-space:nowrap}.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{position:sticky;top:0;background:var(--card);cursor:pointer;user-select:none;font-weight:600;white-space:nowrap}
td.n{text-align:right;font-variant-numeric:tabular-nums}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.pill{display:inline-block;padding:0 6px;border-radius:9px;border:1px solid var(--line);color:var(--muted);font-size:12px}
.bad{color:var(--warn);font-weight:600}.ok{color:var(--good)}.note{color:var(--muted);font-size:12px}
</style></head><body><main>
<h1>Open roles</h1>
<p class="sub" id="sub"></p>
<div id="warn"></div>
<div class="bar"><input type="search" id="q" placeholder="Filter: company, title, location">
<label><input type="checkbox" id="contract"> Contract only</label>
<label><input type="checkbox" id="remote"> Remote only</label>
<label><input type="checkbox" id="fresh"> Posted in last 14 days</label></div>
<div class="wrap"><table><thead><tr>
<th data-k="prio">Priority</th><th data-k="company">Company</th><th data-k="title">Role</th><th data-k="location">Location</th>
<th data-k="type">Type</th><th data-k="posted">Posted</th><th data-k="first_seen">First seen</th><th data-k="source">Source</th>
</tr></thead><tbody id="rows"></tbody></table></div>
<p class="note">Priority: Claude's fit score out of 10 where Claude has scored the role (marked ★), otherwise a rough keyword match (title, contract/remote, Ireland/UK/EU, posted this week). Only roles that pass the sweep's title and location filters are listed. Click a column to sort.</p>
<h2>Job boards swept</h2>
<p class="sub">One board per company: each company publishes its own openings through a hiring system (Greenhouse, Lever, Ashby…). The sweep reads those directly.</p>
<div class="wrap"><table><thead><tr><th>Company</th><th>System</th><th>Open roles</th><th>Matching</th><th>Status</th></tr></thead><tbody id="boards"></tbody></table></div>
</main><script>
const D=__DATA__;const $=s=>document.querySelector(s);const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
D.rows.forEach(r=>r.prio=r.score!=null?100+r.score:r.rough);
$("#sub").textContent=`Sweep of ${D.run_date}: ${D.rows.length} matching roles from ${D.n_ok} company boards.`;
if(D.n_missing)$("#warn").innerHTML=`<div class="warn">${D.n_missing} boards could not be read and are not included (listed at the bottom).</div>`;
let key="prio",dir=-1;const cutoff=new Date(Date.now()-14*864e5).toISOString().slice(0,10);
function draw(){const q=$("#q").value.toLowerCase();
const rs=D.rows.filter(r=>(!q||(r.company+" "+r.title+" "+r.location).toLowerCase().includes(q))
&&(!$("#contract").checked||/contract|freelance|temporary|fixed.term/i.test(r.type+" "+r.title))
&&(!$("#remote").checked||/remote|anywhere/i.test(r.location))&&(!$("#fresh").checked||r.posted>=cutoff))
.sort((a,b)=>(a[key]>b[key]?1:a[key]<b[key]?-1:0)*dir);
$("#rows").innerHTML=rs.map(r=>`<tr><td class="n">${r.score!=null?"★ "+r.score:r.rough}${r.status?` <span class="pill">${esc(r.status)}</span>`:""}</td>
<td>${esc(r.company)}</td><td><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>${r.note?`<div class="note">${esc(r.note)}</div>`:""}</td>
<td>${esc(r.location)}</td><td>${esc(r.type)}</td><td>${esc(r.posted)}</td><td>${esc(r.first_seen)}</td><td>${esc(r.source)}</td></tr>`).join("")||`<tr><td colspan="8" class="note">No roles match the filters.</td></tr>`;}
document.querySelectorAll("th[data-k]").forEach(th=>th.onclick=()=>{const k=th.dataset.k;dir=key===k?-dir:(k==="prio"||k==="posted"||k==="first_seen"?-1:1);key=k;draw();});
["#q","#contract","#remote","#fresh"].forEach(s=>$(s).addEventListener("input",draw));draw();
$("#boards").innerHTML=D.boards.map(b=>`<tr><td>${esc(b.company)}</td><td>${esc(b.source)}</td><td class="n">${b.ok?b.total:"–"}</td><td class="n">${b.ok?b.hits:"–"}</td>
<td>${b.ok?'<span class="ok">read</span>':'<span class="bad">could not read</span>'}</td></tr>`).join("");
</script></body></html>
"""

if __name__ == "__main__":
    print(build())
