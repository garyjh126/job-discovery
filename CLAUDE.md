# job-discovery

Daily sweep of public ATS job-board APIs, plus the playbook an agent follows to score and track roles. README.md covers usage; docs/agent-workflow.md covers the rubric and MCP calls.

- Python 3 standard library only. Run scripts with `python3 -I`. Don't add dependencies.
- The `job_discovery` container bind-mounts this folder at `/app`, so code edits take effect at the next daily run. Changes to `docker-compose.yml` or `.env` need `docker compose config` (check), then `docker compose up -d` (recreate). `docker compose restart` does not pick them up.
- `data/` is private and gitignored, except `data/companies.example.txt`. Never commit `.env`, `data/companies.txt`, `data/runs/`, `seen.json`, `scores.json` or `roles.html`.
- Tests: `python3 -m unittest` from the repo root. They run offline with the network mocked. Add one for any new ATS reader.
- Test a full run without touching real data: copy the scripts and a `data/companies.txt` to a temp folder and run there with `JOB_VAULT=<tmp>` (`daily.py` writes to `<JOB_VAULT>/00 Inbox/`).
- Only public, unauthenticated endpoints that robots.txt allows. Check robots.txt before adding an ATS reader; SmartRecruiters stays disabled. A reader returns `None` when a board can't be read, so the health check reports it rather than the sweep failing.
- `data/scores.json` is written by the agent when it scores roles: `{"<posting url>": {"score": 7, "note": "...", "status": "applied"}}`. `viewer.py` shows it on the roles page.
