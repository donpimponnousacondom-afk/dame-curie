"""Map the recall cut-offs of one embedding model to another with real memory data.

Method: equal pass volume. For each search, the old cut-off passes a fraction p
of all (query, row) pairs in the Qwen space. The new cut-off is the value that
passes the same fraction p in the new space. Queries are real user messages;
each row has a vector in both spaces, so no API call is needed.
Report: how often labelled pairs (a message and the fact extracted from it) pass the
old cut-off in the old space and the new cut-off in the new space.
Usage: python calibrate.py <old db> <old backend id> <new db> <new backend id>
Run it as dame-curie with a Python 3.14 venv that has numpy. It opens both databases read-only.
OLD holds the cut-offs of the old model (the Qwen defaults); edit it when the old model differs.
"""

import json
import sqlite3
import sys

import numpy as np

OLD = {"facts": 0.35, "messages": 0.40, "web": 0.40, "negative": 0.85}


def load(path: str, backend: str) -> dict:
    """Return the embedded rows of one backend, keyed by row id."""
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT id, kind, source, content, embedding, created_at, author_id, channel_id, metadata "
        "FROM vectors WHERE embedding IS NOT NULL AND embedding_backend=?",
        (backend,),
    ).fetchall()
    return {r[0]: r for r in rows}


def matrix(rows: dict, ids: list) -> np.ndarray:
    """Return the unit-length vectors of the given row ids, one row per id."""
    m = np.stack([np.frombuffer(rows[i][4], dtype=np.float32) for i in ids]).astype(
        np.float64
    )
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def main() -> None:
    """Print the calibration report as JSON."""
    qwen, new = load(sys.argv[1], sys.argv[2]), load(sys.argv[3], sys.argv[4])
    if not qwen or not new:
        raise SystemExit(f"no rows: old space {len(qwen)}, new space {len(new)}")
    both = {i for i in qwen if i in new}
    by_kind = {}
    for i in both:
        by_kind.setdefault(qwen[i][1], []).append(i)
    queries = sorted(
        (
            i
            for i in by_kind.get("message", [])
            if qwen[i][2] == "user" and len(qwen[i][3] or "") >= 12
        ),
        key=lambda i: qwen[i][5],
    )[-600:]
    report = {
        "rows_in_both_spaces": len(both),
        "queries": len(queries),
        "kinds": {k: len(v) for k, v in by_kind.items()},
    }
    qq, qn = matrix(qwen, queries), matrix(new, queries)

    def calibrate(name: str, docs: list, exclude_self: bool = False) -> float:
        """Record and return the new cut-off that passes the same pair fraction as the old one."""
        dq, dn = matrix(qwen, docs), matrix(new, docs)
        sq, sn = qq @ dq.T, qn @ dn.T
        if exclude_self:
            pos = {d: j for j, d in enumerate(docs)}
            for a, q in enumerate(queries):
                if q in pos:
                    sq[a, pos[q]] = sn[a, pos[q]] = -2.0
        valid = sq > -2.0
        p = float(np.mean(sq[valid] >= OLD[name]))
        t_new = float(np.quantile(sn[valid], 1.0 - p))
        report[name] = {
            "docs": len(docs),
            "old_cut_off": OLD[name],
            "pass_fraction": round(p, 5),
            "new_cut_off": round(t_new, 3),
            "queries_with_a_hit_old": round(
                float(np.mean((sq >= OLD[name]).any(axis=1))), 3
            ),
            "queries_with_a_hit_new": round(
                float(np.mean((sn >= t_new).any(axis=1))), 3
            ),
            "median_pair_old": round(float(np.median(sq[valid])), 3),
            "median_pair_new": round(float(np.median(sn[valid])), 3),
            "p99_pair_old": round(float(np.quantile(sq[valid], 0.99)), 3),
            "p99_pair_new": round(float(np.quantile(sn[valid], 0.99)), 3),
        }
        return t_new

    t_facts = calibrate("facts", by_kind["ltm"])
    calibrate(
        "messages",
        [i for i in by_kind["message"] if qwen[i][2] == "user"],
        exclude_self=True,
    )
    calibrate("web", by_kind["web_result"])

    # Negative exclusion: near-duplicate tail of fact-to-fact pairs.
    facts = sorted(by_kind["ltm"] + by_kind["shared_context"])
    rng = np.random.default_rng(7)
    sample = list(rng.choice(facts, size=min(3000, len(facts)), replace=False))
    fq, fn = matrix(qwen, sample), matrix(new, sample)
    sq, sn = fq @ fq.T, fn @ fn.T
    upper = np.triu_indices(len(sample), k=1)
    p = float(np.mean(sq[upper] >= OLD["negative"]))
    report["negative"] = {
        "pairs": int(len(upper[0])),
        "old_cut_off": OLD["negative"],
        "pass_fraction": round(p, 6),
        "new_cut_off": round(float(np.quantile(sn[upper], 1.0 - p)), 3),
    }

    # Labelled pairs: a user message and a fact extracted from it 0 to 180 s later.
    msgs = [
        qwen[i]
        for i in by_kind["message"]
        if qwen[i][2] == "user" and len(qwen[i][3] or "") >= 12
    ]
    labelled = []
    for fid in by_kind.get("shared_context", []) + by_kind.get("entity", []):
        f = qwen[fid]
        md = json.loads(f[8] or "{}")
        author = str(md.get("source_user_id") or f[6] or "")
        chan = str(md.get("source_channel_id") or "")
        cands = [
            m
            for m in msgs
            if str(m[6]) == author
            and (not chan or str(m[7]) == chan)
            and 0 <= f[5] - m[5] <= 180
        ]
        if cands:
            labelled.append((max(cands, key=lambda m: m[5])[0], fid))
    if labelled:
        lq = np.array(
            [float(matrix(qwen, [m])[0] @ matrix(qwen, [f])[0]) for m, f in labelled]
        )
        ln = np.array(
            [float(matrix(new, [m])[0] @ matrix(new, [f])[0]) for m, f in labelled]
        )
        report["labelled_pairs"] = {
            "pairs": len(labelled),
            "median_old": round(float(np.median(lq)), 3),
            "median_new": round(float(np.median(ln)), 3),
            "pass_old_at_old_cut_off": round(float(np.mean(lq >= OLD["facts"])), 3),
            "pass_new_at_new_cut_off": round(float(np.mean(ln >= t_facts)), 3),
        }
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
