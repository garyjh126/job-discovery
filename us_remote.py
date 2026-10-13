import json, re, sys, html, urllib.request, urllib.parse
d = json.load(open(sys.argv[1]))
src = {}
for l in open(sys.argv[2]):
    if l.strip() and not l.startswith("#"):
        p = l.split(None, 2); src[p[2].strip() if len(p) > 2 else p[1]] = (p[0], p[1])
TRACK = re.compile(r"machine learning|\bml\b|inference|\bgpu\b|cuda|reinforcement|\brl\b|research engineer|optimi[sz]ation|quant|c\+\+|low.latency|algorithm|multi.agent|simulation|evaluat", re.I)
EU = re.compile(r"ireland|dublin|europe|emea|united kingdom|\buk\b|london|amsterdam|berlin|paris|germany|france|spain|poland", re.I)
REQ_US = re.compile(r"(located|based|reside|residing|live|living) (in|within) the (united states|u\.s\.|us\b)|authori[sz]ed to work in the (united states|u\.s\.|us\b)|u\.s\. (person|citizen)|us citizenship|security clearance|(united states|u\.s\.|us) work authori[sz]ation|remote \((usa|us)\) only|us-based|u\.s\.-based", re.I)
OPEN = re.compile(r"contractor|international|anywhere|worldwide|globally|any (country|location)|outside (of )?the (us|united states)|\bdeel\b|employer of record|\beor\b", re.I)
UA = {"User-Agent": "job-search-personal/1.0"}
def get(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25) as r: return json.loads(r.read())
    except Exception: return None
ashby_cache = {}
def text_for(co, h):
    ats, tok = src.get(co, (None, None))
    if ats == "ashby":
        if tok not in ashby_cache:
            b = get("https://api.ashbyhq.com/posting-api/job-board/" + urllib.parse.quote(tok)) or {}
            ashby_cache[tok] = {j.get("jobUrl"): j.get("descriptionPlain") or "" for j in b.get("jobs", [])}
        return ashby_cache[tok].get(h["url"], "")
    if ats == "gh":
        m = re.search(r"(?:jobs/|gh_jid=|token=)(\d+)", h["url"])
        if m:
            j = get(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs/{m.group(1)}") or get(f"https://boards-api.eu.greenhouse.io/v1/boards/{tok}/jobs/{m.group(1)}")
            return re.sub(r"<[^>]+>", " ", html.unescape(html.unescape((j or {}).get("content", ""))))
    return ""
for co, r in d["results"].items():
    for h in r["hits"]:
        loc = h["location"] or ""
        if re.search(r"remote", loc, re.I) and not EU.search(loc) and TRACK.search(h["title"]):
            t = text_for(co, h)
            req = REQ_US.search(t); op = OPEN.search(t)
            v = "US-REQUIRED" if req else ("OPEN-SIGNAL" if op else ("silent" if t else "NO-TEXT"))
            print(f"{v:12} | {co} | {h['title']} | {loc[:45]} | {h['url']}" + (f" <<{req.group(0)}>>" if req else (f" <<{op.group(0)}>>" if op else "")))
