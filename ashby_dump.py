import json, sys, urllib.request, urllib.parse, re
org = sys.argv[1]; pat = re.compile(sys.argv[2], re.I)
u = "https://api.ashbyhq.com/posting-api/job-board/" + urllib.parse.quote(org) + "?includeCompensation=true"
try:
    d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "job-search-personal/1.0"}), timeout=25).read())
except Exception as e:
    print(org, "ERR", e); sys.exit()
for j in d.get("jobs", []):
    if pat.search(j.get("title", "")):
        comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
        print(f"=== {org} | {j['title']} | {j.get('location')} | remote={j.get('isRemote')} | {j.get('employmentType')} | {j.get('publishedAt','')[:10]} | {comp} | {j.get('jobUrl')}")
        print(re.sub(r"\n\s*\n+", "\n", j.get("descriptionPlain") or "")[:3800]); print()
