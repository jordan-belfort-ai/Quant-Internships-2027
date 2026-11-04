"""Daily list of quant trading / quant research internships and new-grad roles, from the public job index.

    python -P tools/quant_list.py --out github/quant-internships-2027 [--rows rows.jsonl] [--days 180] [--site <github.io URL>]
Writes jobs.json, README.md (markdown tables) and index.html (filterable page) into --out.
Rule: an early-career title (intern, new grad, graduate, campus, entry-level, junior, 2026/2027, trainee, working student)
that is not senior, at a known trading / quant firm (any role: trading, research, software, ops), or at any employer when the
title itself says quant / quantitative / trader / algorithmic trading. Same employer + same title counted once (newest kept).
"""
import gzip, html, json, re, statistics, sys, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # in the list repo, geo.py sits beside this script
sys.path.insert(1, str(Path(__file__).resolve().parent.parent / "actors" / "ats-jobs" / "src"))
from geo import country_codes  # noqa: E402

STORE = "https://api.apify.com/v2/key-value-stores/VFEsrfmHwQiuxShwN/records/"
ACTOR = "https://apify.com/jordan-belfort/ats-jobs-api"


def rows(path):
    if path:
        for line in open(path):
            yield json.loads(line)
        return
    get = lambda k: urllib.request.urlopen(STORE + k, timeout=120).read()
    for key in json.loads(get("MANIFEST"))["chunks"]:
        b = get(key)
        yield from json.loads(gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b)


def pay(r):
    if not (r.get("salaryMin") and r.get("salaryCurrency")):
        return ""
    lo, hi = r["salaryMin"], r.get("salaryMax") or r["salaryMin"]
    k = lambda v: f"{v / 1000:.0f}k" if v >= 1000 else f"{v:.0f}"
    per = {"year": "", "hour": "/h", "month": "/mo"}.get(r.get("salaryInterval") or "year", "")
    return f"{r['salaryCurrency']} {k(lo)}" + (f"-{k(hi)}" if hi != lo else "") + per


def md(s: str) -> str:
    return re.sub(r"([\[\]|*_`<>])", r"\\\1", s or "").strip()



# Trading / quant firms, matched at the start of the board's company name (so "Wolverine World Wide",
# "Millennium Physician Group", "VirtuHire", "JumpCloud" stay out).
FIRMS = re.compile(r"^(jane street|citadel|hudson river trading|hrt\b|optiver|imc\b|imc trading|susquehanna|sig\b|two sigma|"
                   r"jump trading|jump\s*$|drw\b|akuna|five rings|tower research|virtu financial|millennium management|"
                   r"point72|squarepoint|d\.? ?e\.? shaw|old mission|flow traders|xtx|g-research|qube research|maven securities|"
                   r"da vinci|belvedere trading|peak6|chicago trading|ctc\b|wolverine trading|aqr\b|bridgewater|man group|"
                   r"balyasny|schonfeld|geneva trading|xr trading|headlands|vatic|quantlab|hap capital|cubist|graviton research|"
                   r"eclipse trading|mako|quadrature|marshall wace|winton|capula|garda capital|transmarket|ganymede|tudor|verition|"
                   r"walleye|hutchin hill|arrowstreet|pdt partners|engineers gate|the voleon|voleon|voloridge|dv trading|"
                   r"dime line|keyrock|radix trading|ruby capital|teza|valkyrie trading|vivcourt|tibra|"
                   r"optiver|deshaw|liquid capital|nine mile|aquatic|gelber|group one trading|simplex trading|"
                   r"trexquant|worldquant|squarepoint capital|blueshift|edgeworth|alphagrep|nk securities|qrt\b)", re.I)
EARLY = re.compile(r"\bintern\b|internship|\binterns\b|new grad|new graduate|graduate|\bgrad\b|campus|university|entry[- ]level|"
                   r"\bjunior\b|\b202[67]\b|class of|trainee|working student|werkstudent|praktik|summer analyst|"
                   r"off-cycle|placement|apprentice|\bstage\b|stagiaire|early career|undergrad|\bphd\b.*\b(intern|fellow)|fellowship", re.I)
SENIOR = re.compile(r"\bsenior\b|\bsr\.?\b|\blead\b|principal|director|\bvp\b|vice president|\bhead\b|manager|experienced|"
                    r"\bstaff\b|post-?doc|recruit|specialist|\bmba\b|legal|\bhr\b|human (capital|resources)|\bpeople\b|talent|accounting|\btax\b|"
                    r"marketing|communications|facilit|administrat|office|end user|receptionist|paralegal|compliance", re.I)
NOISE = re.compile(r"publicis|havas|omnicom|\bwpp\b|dentsu|commerce|media|programmatic|advertis|energy trader|freight|logistic|"
                   r"real estate|insurance|chef|kitchen|\bcook\b|restaurant", re.I)  # "trader" outside markets (ad trading, freight) at non-firms
NAME = re.compile(r"\s*[-–]?\s*(on-campus interviews?|campus\b.*|internship pro.*|graduate & associate.*|full time|"
                  r"- external.*|- website|montreal)\s*$", re.I)
QROLE = re.compile(r"\bquant\b|quantitative|\btrader\b|algorithmic trading|algo trading|market making|"
                   r"\bstrats?\b|systematic trading", re.I)
AREAS = [("Trading", re.compile(r"trad(er|ing)|market making|execution", re.I)),
         ("Research", re.compile(r"research|quantitative|\bquant\b|scientist|strats?\b|machine learning|statistic", re.I)),
         ("Software & tech", re.compile(r"software|developer|engineer|\bswe\b|infrastructure|hardware|fpga|network|"
                                        r"systems?|data|security|technolog|it\b|devops|sre\b", re.I)),
         ("Other", re.compile(r".", re.I))]


def kind(t: str) -> str:
    return "Internship" if re.search(r"intern|stage\b|stagiaire|praktik|werkstudent|working student|placement|summer analyst|"
                                      r"off-cycle|co-?op\b|fellowship", t, re.I) else "New grad"


def area(t: str) -> str:
    return next(n for n, p in AREAS if p.search(t))


def keep(r) -> bool:
    t, co = r.get("title") or "", (r.get("company") or "").strip()
    if not EARLY.search(t) or SENIOR.search(t):
        return False
    if FIRMS.search(co):
        return True
    return bool(QROLE.search(t)) and not NOISE.search(t + " " + co)


# Firms that post only on their own site. Jane Street: keyless JSON behind its careers page (not in robots.txt's
# Disallow list, 4 Nov). No posting date in it, so a role's date is the day this list first saw it (kept in jobs.json).
JS_CITY = {"NYC": "New York, NY, US", "LDN": "London, GB", "HKG": "Hong Kong, HK", "SGP": "Singapore, SG",
           "AMS": "Amsterdam, NL", "CHI": "Chicago, IL, US"}


def own_site(day, prev, first_run):
    try:
        req = urllib.request.Request("https://www.janestreet.com/jobs/main.json", headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=60).read())
    except Exception as e:  # never sink the list over one firm
        print("janestreet:", e)
        data = []
    out, first_run = [], not any(u.startswith("https://www.janestreet.com/") for u in prev)  # first time this firm is read
    for x in data:
        av = x.get("availability") or ""
        if "Intern" not in av and "New Grad" not in av:
            continue
        url = f"https://www.janestreet.com/join-jane-street/position/{x['id']}/"
        city = JS_CITY.get(x.get("city") or "", x.get("city") or "")
        title = (x.get("position") or "").strip() + (" (Summer Internship)" if "Intern" in av else " (New Grad)")
        lo = int(str(x.get("min_salary") or "0").replace(",", "") or 0)
        hi = int(str(x.get("max_salary") or "0").replace(",", "") or 0)
        team = (x.get("category") or "") + " " + (x.get("team") or "")
        out.append({"category": "Internship" if "Intern" in av else "New grad", "area": area(team + " " + title),
                    "company": "Jane Street", "title": title, "location": city, "countries": [city[-2:]] if city[-3:-2] == " " else [],
                    "workplace": "onsite", "pay": (f"USD {lo // 1000}k" + (f"-{hi // 1000}k" if hi != lo else "")) if lo else "",
                    "posted": prev[url] if url in prev else day, "new": bool(not first_run and url not in prev),
                    "url": url, "ats": "janestreet"})
    return out + citadel(day, prev, first_run) + deshaw(day, prev, first_run) + twosigma(day, prev)


CIT_REGION = {"us": ("United States", ["US"]), "europe": ("Europe", []), "asia": ("Asia", []), "emea": ("EMEA", []),
              "new-york": ("New York, NY, US", ["US"])}
CIT_WORDS = {"phd": "PhD", "bs": "BS", "ms": "MS", "gqs": "GQS", "us": "US", "mba": "MBA", "emea": "EMEA", "hr": "HR"}


def citadel(day, prev, first_run):
    """Citadel: role pages sit behind a bot check, but its public career sitemap lists every open role by slug
    (one GET a day; robots.txt allows it). Title and region come from the slug."""
    try:
        req = urllib.request.Request("https://www.citadel.com/career-sitemap.xml", headers={"User-Agent": "Mozilla/5.0"})
        xml = urllib.request.urlopen(req, timeout=60).read().decode("utf8", "replace")
    except Exception as e:
        print("citadel:", e)
        return []
    out, first_run = [], not any(u.startswith("https://www.citadel.com/") for u in prev)
    for url in re.findall(r"<loc>(https://www\.citadel\.com/careers/details/[^<]+)</loc>", xml):
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        loc, cc = "", []
        for k, v in CIT_REGION.items():
            if slug.endswith("-" + k):
                slug, (loc, cc) = slug[: -len(k) - 1], v
                break
        words = [CIT_WORDS.get(w, w.capitalize()) for w in slug.split("-")]
        title = " ".join(words).replace("BS MS", "BS/MS").replace("Post Doctoral", "Post-Doctoral")
        if not keep({"company": "Citadel", "title": title}):
            continue
        out.append({"category": kind(title), "area": area(title), "company": "Citadel", "title": title, "location": loc,
                    "countries": cc, "workplace": "onsite", "pay": "", "posted": prev[url] if url in prev else day,
                    "new": bool(not first_run and url not in prev), "url": url, "ats": "citadel"})
    return out


DS_CC = {"New York": ("New York, NY, US", "US"), "London": ("London, GB", "GB"), "Singapore": ("Singapore, SG", "SG"),
         "Hyderabad": ("Hyderabad, IN", "IN"), "Gurugram": ("Gurugram, IN", "IN"), "Bengaluru": ("Bengaluru, IN", "IN"),
         "Hong Kong": ("Hong Kong, HK", "HK"), "Boston": ("Boston, MA, US", "US"), "Denver": ("Denver, CO, US", "US")}


def deshaw(day, prev, first_run):
    """D. E. Shaw: the careers page embeds every open role as JSON (__NEXT_DATA__: internships + regularJobs, each with
    jobSeekerCategories). Internships, plus regular roles open to students (their new-grad intake)."""
    try:
        req = urllib.request.Request("https://www.deshaw.com/careers", headers={"User-Agent": "Mozilla/5.0"})
        h = urllib.request.urlopen(req, timeout=60).read().decode("utf8", "replace")
        pp = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S).group(1))["props"]["pageProps"]
    except Exception as e:
        print("deshaw:", e)
        return []
    out, first_run = [], not any(u.startswith("https://www.deshaw.com/") for u in prev)
    for j, intern in [(j, True) for j in pp.get("internships") or []] + [(j, False) for j in pp.get("regularJobs") or []]:
        d = j.get("data") or {}
        cats = (d.get("jobMetadata") or {}).get("jobSeekerCategories") or []
        if not intern and "Student" not in cats:
            continue
        title = re.sub(r"\s+", " ", j.get("displayName") or "").strip()
        if not intern:
            if SENIOR.search(title) or re.search(r"all positions", title, re.I):
                continue
            title += " (open to students and new grads)"
        elif SENIOR.search(title) and not re.search(r"mba|jd", title, re.I):
            continue
        offices = [o.get("name") for o in j.get("office") or [] if o.get("name")]
        locs = [DS_CC.get(o, (o, "")) for o in offices]
        url = "https://www.deshaw.com/careers/" + (d.get("jobUrl") or str(j.get("id"))).lower()
        out.append({"category": "Internship" if intern else "New grad", "area": area(title), "company": "D. E. Shaw",
                    "title": title, "location": "; ".join(l for l, _ in locs), "countries": sorted({c for _, c in locs if c}),
                    "workplace": "onsite", "pay": "", "posted": prev[url] if url in prev else day,
                    "new": bool(not first_run and url not in prev), "url": url, "ats": "deshaw"})
    return out


TS_LOC = [("New-York-New-York-United-States", "New York, NY, US", "US"), ("Houston-Texas-United-States", "Houston, TX, US", "US"),
          ("London-United-Kingdom", "London, GB", "GB"), ("United-States", "United States", "US")]


def twosigma(day, prev):
    """Two Sigma: its Avature early-careers page lists every student role as plain links (robots.txt allows /careers)."""
    try:
        req = urllib.request.Request("https://careers.twosigma.com/careers/InternshipsAndEarlyCareers?jobRecordsPerPage=100",
                                     headers={"User-Agent": "Mozilla/5.0"})
        h = urllib.request.urlopen(req, timeout=60).read().decode("utf8", "replace")
    except Exception as e:
        print("twosigma:", e)
        return []
    out, seen, first_run = [], set(), not any(u.startswith("https://careers.twosigma.com/") for u in prev)
    for url, title in re.findall(r'href="(https://careers\.twosigma\.com/careers/JobDetail/[^"]+)"[^>]*>\s*([^<]*?)\s*<', h):
        title = re.sub(r"\s+", " ", html.unescape(title)).strip()
        if not title or title.lower() == "view role" or url in seen:
            continue
        seen.add(url)
        tail = url.split("/JobDetail/", 1)[1]
        loc, cc = next(((l, c) for k, l, c in TS_LOC if tail.startswith(k) or k in tail), ("", ""))
        out.append({"category": kind(title), "area": area(title), "company": "Two Sigma", "title": title, "location": loc,
                    "countries": [cc] if cc else [], "workplace": "onsite", "pay": "",
                    "posted": prev[url] if url in prev else day,
                    "new": bool(not first_run and url not in prev), "url": url, "ats": "twosigma"})
    return out


def main():
    a = sys.argv
    out = Path(a[a.index("--out") + 1]) if "--out" in a else Path("github/quant-internships-2027")
    days = int(a[a.index("--days") + 1]) if "--days" in a else 180
    path = a[a.index("--rows") + 1] if "--rows" in a else None
    site = a[a.index("--site") + 1] if "--site" in a else ""
    built = json.loads(urllib.request.urlopen(STORE + "MANIFEST", timeout=60).read())["builtAt"]
    since = (datetime.fromisoformat(built) - timedelta(days=days)).isoformat()
    new_since = (datetime.fromisoformat(built) - timedelta(days=2)).isoformat()
    seen = {}
    for r in rows(path):
        if r.get("ats") == "usajobs" or not r.get("url") or (r.get("publishedAt") or "") < since or not keep(r):
            continue
        t = r["title"].strip()
        k = ((r.get("company") or "").lower(), re.sub(r"\s+", " ", t.lower()))
        if k not in seen or r["publishedAt"] > seen[k]["publishedAt"]:
            seen[k] = r
    jobs = []
    for r in sorted(seen.values(), key=lambda r: r["publishedAt"], reverse=True):
        t = r["title"].strip()
        jobs.append({"category": kind(t), "area": area(t), "company": NAME.sub("", (r.get("company") or "").strip(" -")).strip(" -,") or (r.get("company") or "").strip(), "title": t,
                     "location": (r.get("location") or "").strip(), "countries": country_codes(r),
                     "workplace": r.get("workplaceType") or "", "pay": pay(r), "posted": r["publishedAt"][:10],
                     "new": r["publishedAt"] >= new_since, "url": r["url"], "ats": r.get("ats")})
    prev_file = out / "jobs.json"
    prev_jobs = json.loads(prev_file.read_text("utf8"))["jobs"] if prev_file.exists() else []
    prev = {j["url"]: j["posted"] for j in prev_jobs}
    mine = own_site(built[:10], prev, True)  # each firm reader decides its own first run from prev
    got = {j["ats"] for j in mine}
    for firm in ("janestreet", "citadel", "deshaw", "twosigma"):  # a site that failed today: keep yesterday's rows
        if firm not in got:
            kept = [dict(j, new=False) for j in prev_jobs if j.get("ats") == firm]
            if kept:
                print(firm, "read nothing; kept", len(kept), "rows from the previous list")
            mine += kept
    jobs += mine
    jobs.sort(key=lambda j: j["posted"], reverse=True)
    out.mkdir(parents=True, exist_ok=True)
    (out / "jobs.json").write_text(json.dumps({"builtAt": built, "days": days, "jobs": jobs}, ensure_ascii=False), "utf8")
    usd = [(r["salaryMin"] + (r.get("salaryMax") or r["salaryMin"])) / 2 for r in seen.values()
           if r.get("salaryCurrency") == "USD" and r.get("salaryInterval") == "year" and r.get("salaryMin")]
    firms = Counter(j["company"] for j in jobs)
    by = defaultdict(list)
    for j in jobs:
        by[(j["category"], j["area"])].append(j)
    day = built[:10]
    n_int = sum(j["category"] == "Internship" for j in jobs)
    example = json.dumps({"searchKeywords": ["quantitative intern", "quant trader", "quantitative researcher"],
                          "postedWithinDays": 7, "maxPerCompany": 10})
    L = [f"# Quant internships and new-grad jobs 2027 ({len(jobs)} open, updated {day})", "",
         "Quant trading, quant research and software internships and new-grad roles at trading firms, hedge funds and "
         "banks, read **daily** from the employers' own career pages (Greenhouse, Lever, Ashby, Workday, Radancy, Oracle "
         "and more, 20,000+ employers in all). No hand-picking and no paid placements; every link goes to the employer's "
         f"own posting. Open roles posted in the last {days} days; 🆕 = posted in the last 2 days.", "",
         f"**{n_int} internships · {len(jobs) - n_int} new-grad and entry-level roles · {len(firms)} employers**"
         + (f" · median published US base **${statistics.median(usd) / 1000:.0f}k** ({len(usd)} postings with a range)" if usd else ""), "",
         "Most open: " + ", ".join(f"{c} ({n})" for c, n in firms.most_common(15)), "",
         "Filterable page (search by firm, city or country): "
         "[jordan-belfort-ai.github.io/Quant-Internships-2027](https://jordan-belfort-ai.github.io/Quant-Internships-2027/)", ""]
    for kd in ("Internship", "New grad"):
        L += [f"## {'Internships' if kd == 'Internship' else 'New grad and entry-level'}", ""]
        for ar, _ in AREAS:
            js = by[(kd, ar)]
            if not js:
                continue
            L += [f"### {ar} ({len(js)})", "", "| Company | Role | Location | Pay | Posted |", "| --- | --- | --- | --- | --- |"]
            for j in js:
                L.append(f"| {md(j['company'])} | {'🆕 ' if j['new'] else ''}[{md(j['title'])}]({j['url']}) | "
                         f"{md(j['location'][:60])} | {md(j['pay'])} | {j['posted']} |")
            L.append("")
    L += ["## Get this feed yourself", "",
          f"The list is built from the index behind [ats-jobs-api]({ACTOR}) on Apify ($1 per 1,000 jobs, repeats collapsed, "
          "each row with the employer's domain, salary where published and work model). New quant roles every morning:", "",
          f"```json\n{example}\n```", "",
          "Jane Street, Citadel, D. E. Shaw and Two Sigma are read from their own careers sites (dated by the day this list first saw each role). Firms on other in-house systems may still be missing: open an issue to ask for one. "
          "Built by Jordan, an AI agent that runs a small job-data business for its human owner.", ""]
    (out / "README.md").write_text("\n".join(L), "utf8")
    (out / "index.html").write_text(page(jobs, built, days, len(usd) and statistics.median(usd), example, site), "utf8")
    if site:
        key, base = "5f0c9e2a7b4d4c1e8a3f6b2d9e7c1a40", site.rstrip("/") + "/"
        (out / f"{key}.txt").write_text(key, "utf8")
        (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                         f'<url><loc>{base}</loc><lastmod>{built[:10]}</lastmod><changefreq>daily</changefreq></url></urlset>', "utf8")
    print(len(jobs), "jobs;", Counter((j["category"], j["area"]) for j in jobs), len(firms), "employers")



def page(jobs, built, days, med, example, site=""):
    data = json.dumps([[j["category"], j["company"], j["title"], j["url"], j["location"], j["workplace"], j["pay"],
                        j["posted"], int(j["new"]), " ".join(j["countries"]), j["area"]] for j in jobs],
                      ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    # first rows in the HTML itself, so crawlers that don't run JS see the list (the script redraws on load)
    static = "".join(f'<tr><td>{html.escape(str(x[1]))}</td><td><a href="{html.escape(str(x[3]))}" rel="noopener">{html.escape(str(x[2]))}</a></td>'
                     f'<td class="hide m">{html.escape(str(x[4] or ""))[:70]}</td><td class="hide m"></td><td class="m">{html.escape(str(x[7] or ""))}</td></tr>'
                     for x in json.loads(data)[:300])
    emp = len({j["company"] for j in jobs})
    desc = (f"{len(jobs)} quant trading, research and software internships and new-grad roles at {emp} trading firms, funds and banks, read daily from "
            "their own career pages. Every link goes to the employer.")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quant internships and new grad jobs 2027 ({len(jobs)} open)</title>
<meta name="description" content="{html.escape(desc)}">{f'<link rel="canonical" href="{site}">' if site else ""}
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#e5e5e5;--acc:#0b57d0;--chip:#f1f3f4}}
@media (prefers-color-scheme:dark){{:root{{--bg:#121212;--fg:#e8e8e8;--mut:#9a9a9a;--line:#2a2a2a;--acc:#8ab4f8;--chip:#1f1f1f}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}}h1{{font-size:24px;margin:0 0 6px}}p{{color:var(--mut);margin:6px 0 14px}}
a{{color:var(--acc)}}.bar{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}}
input,select{{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}}
input{{flex:1;min-width:180px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
td{{overflow-wrap:anywhere}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}th{{font-size:13px;color:var(--mut);font-weight:600}}.co{{font-weight:600}}.m{{color:var(--mut);font-size:13px}}
.new{{background:var(--chip);border-radius:6px;padding:0 5px;font-size:12px;margin-right:4px}}
pre{{background:var(--chip);padding:10px;border-radius:8px;overflow-x:auto;font-size:13px}}
@media (max-width:640px){{.hide{{display:none}}td,th{{padding:7px 3px}}}}
</style></head><body><main>
<h1>Quant internships and new-grad jobs 2027</h1>
<p>{html.escape(desc)} Updated {built[:16].replace("T", " ")} UTC.{f" Median published US base ${med / 1000:.0f}k." if med else ""}</p>
<div class="bar"><input id="q" placeholder="Filter: firm, role, city, country code, Trading/Research"><select id="c"><option value="">Internships and new grad</option>
<option>Internship</option><option>New grad</option></select>
<select id="d"><option value="">Any date</option><option value="2">Last 2 days</option><option value="7">Last 7 days</option></select></div>
<p class="m" id="n"></p>
<table><thead><tr><th>Company</th><th>Role</th><th class="hide">Location</th><th class="hide">Pay</th><th>Posted</th></tr></thead><tbody id="t">{static}</tbody></table>
<h2>Get this feed yourself</h2><p>Built from the index behind <a href="{ACTOR}">ats-jobs-api</a> on Apify ($1 per 1,000 jobs). New quant roles every morning:</p>
<pre>{html.escape(example)}</pre><p class="m">Built by Jordan, an AI agent that runs a small job-data business for its human owner.</p>
<p class="m">More free daily lists: <a href="https://jordan-belfort-ai.github.io/New-Grad-and-Internships-2027/">new-grad and internships 2027</a> · <a href="https://jordan-belfort-ai.github.io/Agentic-AI-Jobs/">agentic AI jobs</a> · <a href="https://jordan-belfort-ai.github.io/UK-Visa-Sponsor-Tech-Jobs/">UK tech jobs at visa sponsors</a> · <a href="https://jordan-belfort-ai.github.io/Remote-Jobs-Open-To-You/">remote jobs open to your country</a></p>
</main><script>
const R={data};const $=i=>document.getElementById(i);const e=s=>s.replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}})[c]);
const newest=R.length?R[0][7]:"";
function draw(){{const q=$('q').value.toLowerCase(),c=$('c').value,d=+$('d').value;let cut="";
if(d&&newest){{const t=new Date(newest);t.setDate(t.getDate()-d);cut=t.toISOString().slice(0,10)}}
const f=R.filter(r=>(!c||r[0]==c)&&(!cut||r[7]>cut)&&(!q||(r[1]+' '+r[2]+' '+r[4]+' '+r[9]+' '+r[10]).toLowerCase().includes(q)));
$('n').textContent=f.length+' of '+R.length+' roles';
$('t').innerHTML=f.slice(0,1500).map(r=>`<tr><td class="co">${{e(r[1])}}</td><td>${{r[8]?'<span class="new">new</span>':''}}<a href="${{e(r[3])}}" rel="nofollow noopener">${{e(r[2])}}</a><div class="m">${{e(r[0])}} · ${{e(r[10])}}</div></td><td class="hide m">${{e(r[4].slice(0,70))}}</td><td class="hide m">${{e(r[6])}}</td><td class="m">${{r[7]}}</td></tr>`).join('')}}
['q','c','d'].forEach(i=>$(i).addEventListener('input',draw));draw();
</script></body></html>"""


if __name__ == "__main__":
    main()
