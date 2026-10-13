"""Daily sweep: run ats_sweep, keep only roles not seen before, write them to the vault inbox.

Usage: python3 -I daily.py            (normal daily run)
       python3 -I daily.py --baseline (record everything currently open as seen, write no note)

Files:
  data/runs/YYYY-MM-DD.json  raw sweep output for that day
  data/seen.json             url -> first-seen date, so each role is reported once
  <vault>/00 Inbox/New roles YYYY-MM-DD.md   written every run: new roles plus a sweep-health warning
  data/roles.html            all open matching roles, sorted by priority (viewer.py)
"""
import datetime, json, os, pathlib, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_DIR = os.environ.get("HOST_DIR") or HERE  # this folder as the host sees it (differs inside Docker)
VAULT = os.environ.get("JOB_VAULT", os.path.expanduser("~/Documents/Obsidian Vault"))
TODAY = datetime.date.today().isoformat()

EU = re.compile(r"ireland|dublin|cork|galway|limerick|europe|emea|anywhere|worldwide|united kingdom|\buk\b|\bgb\b|"
                r"london|amsterdam|berlin|paris|zurich|lisbon|barcelona|madrid|munich|warsaw|copenhagen|stockholm|"
                r"belfast|edinburgh|cambridge|oxford|georgia|tbilisi|netherlands|germany|france|spain|portugal|"
                r"poland|switzerland", re.I)
REMOTE = re.compile(r"remote|anywhere", re.I)
US_ONLY = re.compile(r"united states|\busa?\b|us-remote|remote in (the )?us|remote from the us|canada|\b[A-Z]{2}, (USA|US)\b", re.I)
TRACK = re.compile(r"machine learning|\bml\b|\bai\b|inference|\bgpu\b|cuda|reinforcement|\brl\b|research engineer|"
                   r"applied scientist|optimi[sz]ation|quant|c\+\+|low.latency|algorithm|multi.agent|performance|"
                   r"simulation|ai engineer|backend|back-end", re.I)
JUNIOR = re.compile(r"intern\b|internship|graduate|new grad|junior|campus|early careers|20\d\d grads|phd resident", re.I)
NOT_TRACK = re.compile(r"quant(itative)? researcher|quant researcher|trader\b|trading analyst|strategist|"
                       r"manager\b|director|head of", re.I)
CONTRACT = re.compile(r"contract|freelance|temporary|fixed.term", re.I)


def previous_run(today_file):
    runs = sorted(f for f in os.listdir(os.path.join(HERE, "data", "runs")) if f.endswith(".json"))
    earlier = [f for f in runs if f < os.path.basename(today_file)]
    return json.load(open(os.path.join(HERE, "data", "runs", earlier[-1]))) if earlier else None


def health(run, prev, n_boards):
    """Problems worth shouting about. Each is one line for the note and the Docker log."""
    problems = []
    if run["missing"]:
        problems.append(f"{len(run['missing'])} of {n_boards} boards could not be read: " + ", ".join(sorted(run["missing"])))
    if prev:
        newly = sorted(set(run["missing"]) - set(prev["missing"]))
        if newly:
            problems.append("Readable yesterday, failed today: " + ", ".join(newly))
        dropped = sorted(c for c, r in run["results"].items()
                         if r["total"] == 0 and prev["results"].get(c, {}).get("total", 0) > 0)
        if dropped:
            problems.append("Board read but now lists 0 open roles (moved or broken?): " + ", ".join(dropped))
    if not any(r["hits"] for r in run["results"].values()):
        problems.append("No matching roles on any board: the sweep or the filters are probably broken")
    return problems


def write_note(lines):
    out = os.path.join(VAULT, "00 Inbox", f"New roles {TODAY}.md")
    open(out, "w").write("\n".join(lines) + "\n")
    return out


def main():
    os.makedirs(os.path.join(HERE, "data", "runs"), exist_ok=True)
    run_file = os.path.join(HERE, "data", "runs", f"{TODAY}.json")
    companies = os.path.join(HERE, "data", "companies.txt")
    n_boards = sum(1 for l in open(companies) if l.strip() and not l.startswith("#"))
    try:
        subprocess.run([sys.executable, "-I", os.path.join(HERE, "ats_sweep.py"), companies, run_file],
                       check=True, stdout=subprocess.DEVNULL)
        run = json.load(open(run_file))
    except Exception as e:
        print(f"ERROR: sweep failed: {e!r}", flush=True)
        write_note(["---", "tags: [job-search, inbox]", "---", f"# New roles {TODAY}", "",
                    f"> [!danger] The sweep failed\n> `{e!r}`\n> Check `docker logs job_discovery`. No roles were read today."])
        raise
    results = run["results"]
    problems = health(run, previous_run(run_file), n_boards)
    for p in problems:
        print(f"ERROR: {p}", flush=True)

    seen_file = os.path.join(HERE, "data", "seen.json")
    seen = json.load(open(seen_file)) if os.path.exists(seen_file) else {}

    new = []
    for company, r in results.items():
        for h in r["hits"]:
            url = h["url"]
            if not url or url in seen:
                continue
            seen[url] = TODAY
            loc = h["location"] or ""
            in_region = EU.search(loc) or (REMOTE.search(loc) and not US_ONLY.search(loc))
            if JUNIOR.search(h["title"]) or NOT_TRACK.search(h["title"]) or not TRACK.search(h["title"]) or not in_region:
                continue
            new.append((company, h))
    json.dump(seen, open(seen_file, "w"), indent=0)

    # The roles page is a convenience; a failure there is logged but never stops the sweep.
    if subprocess.run([sys.executable, "-I", os.path.join(HERE, "viewer.py")], stdout=subprocess.DEVNULL).returncode:
        print("ERROR: roles page (data/roles.html) not rebuilt", flush=True)

    if "--baseline" in sys.argv:
        print(f"Baseline: {len(seen)} roles recorded as seen.")
        return

    n_hits = sum(len(r["hits"]) for r in results.values())
    status = (f"Read {len(results)} of {n_boards} company boards; {n_hits} open roles match the filters; "
              f"{len(new)} are new since the last sweep. All open matches, sorted by priority: "
              f"[roles page]({pathlib.Path(HOST_DIR, 'data', 'roles.html').as_uri()}).")
    lines = ["---", "tags: [job-search, inbox]", "---", f"# New roles {TODAY}", "", status, ""]
    if problems:
        lines += ["> [!warning] Sweep problems"] + [f"> - {p}" for p in problems] + [""]

    if new:
        new.sort(key=lambda x: (not CONTRACT.search(x[1]["type"] or ""), x[0].lower()))
        lines += ["Not scored yet: ask Claude to \"score today's new roles\". Contract roles are listed first.", "",
                  "| Company | Role | Location | Type | Posted |", "|---|---|---|---|---|"]
        for company, h in new:
            loc = (h["location"] or "").replace("|", "/")[:60]
            lines.append(f"| {company} | [{h['title'].replace('|', '/')}]({h['url']}) | {loc} | {h['type'] or ''} | {h['date']} |")
    else:
        lines.append("No new roles today.")
    manual = [l.split(":", 1)[1].strip().split(" | ") for l in open(companies) if l.startswith("# manual:")]
    if manual:
        lines += ["", "Not swept automatically, check by hand now and then: " +
                  ", ".join(f"[{m[0]}]({m[1]})" for m in manual) + "."]
    out = write_note(lines)
    print(f"{TODAY}: {len(new)} new roles, {len(problems)} problems -> {out}")


if __name__ == "__main__":
    main()
