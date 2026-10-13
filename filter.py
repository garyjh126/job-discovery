import json, re, sys
d = json.load(open(sys.argv[1]))
EU = re.compile(r"ireland|dublin|europe|emea|anywhere|worldwide|united kingdom|\buk\b|london|amsterdam|berlin|paris|zurich|lisbon|barcelona|madrid|munich|warsaw|copenhagen|stockholm|cork|galway|belfast|edinburgh|cambridge|oxford|georgia|tbilisi|netherlands|germany|france|spain|portugal|poland|switzerland", re.I)
REMOTE_ANY = re.compile(r"^\s*remote\s*$|remote\s*[-(]?\s*(global|worldwide|anywhere|emea|europe|eu)", re.I)
TRACK = re.compile(r"machine learning|\bml\b|inference|\bgpu\b|cuda|reinforcement|\brl\b|research engineer|applied scientist|optimi[sz]ation|quant|c\+\+|low.latency|algorithm|multi.agent|performance|simulation|ai engineer|backend|back-end", re.I)
SENIOR_X = re.compile(r"\bstaff\b|principal|lead\b|senior|sr\.?|\bii\b|\biii\b|engineer|developer|scientist", re.I)
rows = []
for co, r in d["results"].items():
    for h in r["hits"]:
        loc = h["location"] or ""
        if not (EU.search(loc) or REMOTE_ANY.search(loc)): continue
        if not TRACK.search(h["title"]): continue
        rows.append((co, h))
for co, h in rows:
    print(f"{co} | {h['title']} | {h['location'][:70]} | {h['type']} | {h['date']} | {h['url']}")
print(len(rows), "rows", file=sys.stderr)
