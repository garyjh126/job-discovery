import json, re, sys, html, urllib.request
UA = {"User-Agent": "job-search-personal/1.0"}
def get(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return None
def strip(h):
    h = html.unescape(h or "")
    h = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", h); h = re.sub(r"<li[^>]*>", "- ", h)
    h = re.sub(r"<[^>]+>", "", html.unescape(h)); return re.sub(r"\n\s*\n+", "\n", h).strip()
out_dir = sys.argv[2]
for line in open(sys.argv[1]):
    if not line.strip(): continue
    key, ats, token, jid = line.split()
    text, meta = None, ""
    if ats == "gh":
        for host in ("boards-api.greenhouse.io", "boards-api.eu.greenhouse.io"):
            d = get(f"https://{host}/v1/boards/{token}/jobs/{jid}")
            if d:
                text = strip(d.get("content")); meta = f"{d.get('title')} | {(d.get('location') or {}).get('name')} | updated {d.get('updated_at','')[:10]} | {d.get('absolute_url')}"; break
    elif ats == "ashby":
        d = get(f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true")
        for j in (d or {}).get("jobs", []):
            if j.get("id") == jid:
                text = j.get("descriptionPlain"); comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
                meta = f"{j.get('title')} | {j.get('location')} | remote={j.get('isRemote')} | {j.get('employmentType')} | published {j.get('publishedAt','')[:10]} | {comp} | {j.get('jobUrl')}"
    open(f"{out_dir}/{key}.txt", "w").write((meta + "\n\n" + (text or "NOT FOUND")))
    print(key, "OK" if text else "MISSING", len(text or ""))
