"""Sweep public ATS job-board APIs (Greenhouse, Lever, Ashby) for matching roles.

Usage: python3 -I ats_sweep.py companies.txt out.json
companies.txt lines: <ats> <token> [display name]
ats: gh | lever | ashby | workable | recruitee | personio | workday  (smartrecruiters disabled: robots.txt)
workday token: <host>/<tenant>/<site>, e.g. salesforce.wd12/salesforce/External_Career_Site
"""
import json, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "job-search-personal/1.0 (+contact via owner)"}

TITLE = re.compile(
    r"machine learning|\bml\b|\bmle\b|inference|\bgpu\b|cuda|reinforcement|\brl\b|research engineer|"
    r"applied scientist|optimi[sz]ation|quant|c\+\+|low.latency|algorithm|game ai|multi.agent|"
    r"backend|back-end|platform engineer|performance engineer|ai engineer|simulation",
    re.I)
EXCLUDE = re.compile(r"intern\b|internship|graduate|new grad|junior|manager|director|head of|recruit|"
                     r"sales|account exec|marketing|legal|counsel|designer|phd resident|student", re.I)
LOC = re.compile(r"ireland|dublin|remote|europe|emea|anywhere|worldwide|united kingdom|\buk\b|london|"
                 r"amsterdam|berlin|paris|zurich|lisbon|barcelona|madrid|munich|warsaw|copenhagen|stockholm|"
                 r"cork|galway|belfast|edinburgh|cambridge|oxford|tbilisi|georgia", re.I)


def get(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # one flaky board (timeouts, truncated reads, bad JSON) must not stop the sweep
        return None


def greenhouse(token):
    d = get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    if not d:
        return None
    return [dict(title=j.get("title", ""), location=(j.get("location") or {}).get("name", ""),
                 type="", date=(j.get("updated_at") or "")[:10], url=j.get("absolute_url", ""))
            for j in d.get("jobs", [])]


def lever(token):
    for host in ("api.lever.co", "api.eu.lever.co"):
        d = get(f"https://{host}/v0/postings/{token}?mode=json")
        if isinstance(d, list):
            out = []
            for j in d:
                c = j.get("categories") or {}
                ts = j.get("createdAt")
                out.append(dict(title=j.get("text", ""),
                                location=" / ".join(filter(None, [c.get("location", ""), j.get("workplaceType", "")])),
                                type=c.get("commitment", ""),
                                date=time.strftime("%Y-%m-%d", time.gmtime(ts / 1000)) if ts else "",
                                url=j.get("hostedUrl", "")))
            return out
    return None


def ashby(token):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true")
    if not d:
        return None
    out = []
    for j in d.get("jobs", []):
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations", []) or []]
        if j.get("isRemote"):
            locs.append("Remote")
        out.append(dict(title=j.get("title", ""), location=" / ".join(filter(None, locs)),
                        type=j.get("employmentType", ""), date=(j.get("publishedAt") or "")[:10],
                        url=j.get("jobUrl", "")))
    return out


def workable(token):
    d = get(f"https://apply.workable.com/api/v1/widget/accounts/{token}")
    if not d:
        return None
    out = []
    for j in d.get("jobs", []):
        locs = [", ".join(filter(None, [l.get("city", ""), l.get("country", "")])) for l in j.get("locations") or []]
        if j.get("telecommuting"):
            locs.append("Remote")
        out.append(dict(title=j.get("title", ""), location=" / ".join(filter(None, locs)),
                        type=j.get("employment_type", ""), date=(j.get("published_on") or "")[:10],
                        url=j.get("url", "")))
    return out


def smartrecruiters(token):
    out, offset = [], 0
    while True:
        d = get(f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset={offset}")
        if not d:
            return out or None
        for j in d.get("content", []):
            loc = j.get("location") or {}
            where = loc.get("fullLocation") or ", ".join(filter(None, [loc.get("city", ""), loc.get("country", "")]))
            if loc.get("remote"):
                where += " / Remote"
            out.append(dict(title=j.get("name", ""), location=where,
                            type=(j.get("typeOfEmployment") or {}).get("label", ""),
                            date=(j.get("releasedDate") or "")[:10],
                            url=f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}"))
        offset += 100
        if offset >= d.get("totalFound", 0):
            return out


def recruitee(token):
    d = get(f"https://{token}.recruitee.com/api/offers/")
    if not d:
        return None
    return [dict(title=j.get("title", ""),
                 location=(j.get("location") or "") + (" / Remote" if j.get("remote") else ""),
                 type=j.get("employment_type_code", ""), date=(j.get("published_at") or "")[:10],
                 url=j.get("careers_url", "")) for j in d.get("offers", [])]


def personio(token):
    import xml.etree.ElementTree as ET
    req = urllib.request.Request(f"https://{token}.jobs.personio.de/xml", headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            root = ET.fromstring(r.read())
    except Exception:
        return None
    out = []
    for p in root.findall("position"):
        t = lambda k: (p.findtext(k) or "").strip()
        out.append(dict(title=t("name"), location=t("office"),
                        type=" ".join(filter(None, [t("employmentType"), t("schedule")])),
                        date=t("createdAt")[:10], url=f"https://{token}.jobs.personio.de/job/{t('id')}"))
    return out


def workday(token):
    """Workday's public job API (the one its careers pages call). robots.txt allows it (checked 2026-10-11)."""
    import datetime
    host, tenant, site = token.split("/")
    url = f"https://{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    out, offset, total, today = [], 0, None, datetime.date.today()
    while offset < 2000:
        body = json.dumps({"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""}).encode()
        req = urllib.request.Request(url, data=body, headers={**UA, "Content-Type": "application/json",
                                                              "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            return out or None
        if total is None:
            total = d.get("total", 0)  # only the first page reports it; later pages say 0
        for j in d.get("jobPostings", []):
            posted = (j.get("postedOn") or "").lower()  # "Posted Today", "Posted 3 Days Ago", "Posted 30+ Days Ago"
            n = 0 if "today" in posted else 1 if "yesterday" in posted else int((re.findall(r"\d+", posted) or [0])[0])
            out.append(dict(title=j.get("title", ""), location=j.get("locationsText", ""), type="",
                            date=(today - datetime.timedelta(days=n)).isoformat() if posted else "",
                            url=f"https://{host}.myworkdayjobs.com/en-US/{site}{j.get('externalPath', '')}"))
        offset += 20
        if offset >= total:
            return out
    return out


# smartrecruiters() is kept for reference but not enabled: api.smartrecruiters.com/robots.txt
# disallows all crawlers except LinkedInBot (checked 2026-10-11). Check SmartRecruiters
# employers through web search or by hand instead.
FN = {"gh": greenhouse, "lever": lever, "ashby": ashby, "workable": workable,
      "recruitee": recruitee, "personio": personio, "workday": workday}


def run(line):
    parts = line.split(None, 2)
    ats, token = parts[0], parts[1]
    name = parts[2] if len(parts) > 2 else token
    jobs = FN[ats](token)
    if jobs is None:
        return name, None
    if "--all" in sys.argv:
        return name, (len(jobs), jobs)
    hits = [j for j in jobs if TITLE.search(j["title"]) and not EXCLUDE.search(j["title"])
            and LOC.search(j["location"] or "")]
    return name, (len(jobs), hits)


def main():
    lines = [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(run, lines))
    out, missing = {}, []
    for name, res in results:
        if res is None:
            missing.append(name)
            continue
        total, hits = res
        out[name] = {"total": total, "hits": hits}
    json.dump({"results": out, "missing": missing}, open(sys.argv[2], "w"), indent=1)
    for name, r in out.items():
        print(f"\n## {name} ({r['total']} open, {len(r['hits'])} match)")
        for h in r["hits"]:
            print(f"- {h['title']} | {h['location']} | {h['type']} | {h['date']} | {h['url']}")
    print("\nNOT FOUND:", ", ".join(missing))


if __name__ == "__main__":
    main()
