#!/usr/bin/env python3
"""mimo.xiaomi.com RL dashboard puller. Plain REST, no auth. Formats for chat.

Usage:
  python3 mimo.py                 # everything, once
  python3 mimo.py status|bench|live|notices
  python3 mimo.py watch [interval_s] [max_polls]   # print only on change
"""
import json, sys, time, urllib.request

BASE = "https://mimo.xiaomi.com/rl/api"
UA = {"User-Agent": "Mozilla/5.0 (compatible; mimo-fetch/1.0)"}
RUNS = ("pro", "flash")


def get(path):
    req = urllib.request.Request(BASE + path, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def hhmmss(sec):
    sec = int(max(0, sec))
    return "%dh%02dm" % (sec // 3600, (sec % 3600) // 60)


def run_line(run):
    st = get("/status?run=" + run)
    step, tot = st["step"], st["totals"]
    hl = st.get("headline", {})
    left = step["expected"] - step["since"]
    return ("{:<5} step {:>2} done, on {:>2} ({}, {:>3}%)  dynsam {:.4f}  "
            "eta {:<7} ${:,.0f}  restarts {}").format(
        run, step["last"], step["last"] + 1, step["phase"],
        int(round(step["progress"] * 100)), hl.get("last", 0),
        hhmmss(left), st["cost"]["so_far"], tot["restarts"])


def bench_line():
    b = get("/benchmarks")["benchmarks"][0]
    out = []
    for run in RUNS:
        res = b["results"][run]
        k = sorted(res, key=lambda s: int(s))
        out.append("{} {:.2f} @ s{} (n={})".format(run, res[k[-1]], k[-1], len(k)))
    return b["title"] + "  " + " | ".join(out)


def notice_lines(n=3):
    ns = get("/notices")["notices"][:n]
    return ["{}  {}".format(time.strftime("%H:%M", time.gmtime(x["t"])), x["text"]) for x in ns]


def live_line(run):
    lv = get("/live?run=" + run)["latest"]
    return ("{:<5} passrate {:.3f}  judged {}/{}  accept {}  working {}  "
            "remain {} (+{} partial)  prewarm {}").format(
        run, lv["passrate"], lv["judged"], lv["judged_of"], lv["accept"],
        lv["working"], lv["remain"], lv["remain_partial"], lv["prewarm"])


def fingerprint():
    """(step numbers, restart counts) - what actually counts as an event."""
    fp = {}
    for run in RUNS:
        st = get("/status?run=" + run)
        fp[run] = (st["step"]["last"], st["totals"]["restarts"])
    return fp


def snapshot(which):
    print("mimo RL @ " + time.strftime("%H:%M:%S UTC", time.gmtime()))
    if "all" in which or "status" in which:
        for r in RUNS:
            print(run_line(r))
    if "all" in which or "bench" in which:
        print(bench_line())
    if "all" in which or "live" in which:
        for r in RUNS:
            print(live_line(r))
    if "all" in which or "notices" in which:
        for l in notice_lines():
            print("notice " + l)


def watch(interval=120, max_polls=30):
    print("watching every {}s, max {} polls @ {}".format(
        interval, max_polls, time.strftime("%H:%M:%S UTC", time.gmtime())))
    prev = fingerprint()
    for r in RUNS:
        print("baseline " + run_line(r))
    for i in range(max_polls):
        time.sleep(interval)
        try:
            cur = fingerprint()
        except Exception as e:
            print("poll {} error: {}".format(i + 1, e))
            continue
        changed = [r for r in RUNS if cur.get(r) != prev.get(r)]
        if changed:
            for r in changed:
                print("CHANGE " + run_line(r))
            return 0
    print("no change in {} polls".format(max_polls))
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "watch":
        iv = int(args[1]) if len(args) > 1 else 120
        mp = int(args[2]) if len(args) > 2 else 30
        sys.exit(watch(iv, mp))
    snapshot(args or ["all"])
