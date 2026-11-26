#!/usr/bin/env python3
"""Turn the CSV from run_eval.py into tables, statistics and a plot for the paper.

    uv run --project solutions/project_fuzz --group eval python solutions/project_fuzz/experiments/summarize.py results.csv --outdir results

Prints Markdown tables and writes, into --outdir:
    tables.tex     LaTeX tables (booktabs, works with acmart)
    progress.pdf   failures found vs. executions, per mode (also .png)

Definitions
    target    a (method, outcome) pair that the method can actually produce (@Case)
    failure   a target whose outcome is not "ok" and not "*" (hitting the step
              limit does not prove non-termination, so "*" is reported apart)
    excluded  methods the interpreter cannot run at all in any mode (every
              execution crashed, or a parameter type the fuzzer cannot generate);
              no mode can find anything there, so they would only add noise

Statistics compare the modes across seeds: Mann-Whitney U (two-sided) and the
Vargha-Delaney A12 effect size. A12(X, Y) is the probability that a run of X
does better than a run of Y: 0.5 = no difference, >= 0.71 is usually called a
large effect, >= 0.64 medium, >= 0.56 small.
"""

import argparse
import csv
import statistics as st
from collections import defaultdict
from itertools import combinations
from pathlib import Path

MODE_ORDER = ["random", "coverage", "full"]
FAILED_STATUS = {"unsupported", "all-crashed", "hung"}


def a12(xs, ys) -> float:
    """Probability that a value from xs is larger than one from ys (ties count half)."""
    gt = sum(1 for x in xs for y in ys if x > y)
    eq = sum(1 for x in xs for y in ys if x == y)
    return (gt + 0.5 * eq) / (len(xs) * len(ys))


def mwu(xs, ys) -> float:
    """Two-sided Mann-Whitney U p-value (1.0 if the samples are identical)."""
    if len(set(xs) | set(ys)) == 1:
        return 1.0
    from scipy.stats import mannwhitneyu

    return float(mannwhitneyu(xs, ys, alternative="two-sided").pvalue)


def effect(a: float) -> str:
    d = abs(a - 0.5)
    return "large" if d >= 0.21 else "medium" if d >= 0.14 else "small" if d >= 0.06 else "negligible"


def fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def md_table(header, rows) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def tex_table(caption, label, header, rows, align=None) -> str:
    align = align or "l" + "r" * (len(header) - 1)
    esc = lambda s: str(s).replace("_", r"\_").replace("%", r"\%").replace("#", r"\#").replace("<", r"$<$").replace("±", r"$\pm$")
    body = "\n".join("    " + " & ".join(esc(c) for c in r) + r" \\" for r in rows)
    return (
        "\\begin{table}[t]\n  \\small\n"
        f"  \\caption{{{caption}}}\n  \\label{{{label}}}\n"
        f"  \\begin{{tabular}}{{{align}}}\n    \\toprule\n"
        f"    {' & '.join(esc(h) for h in header)} \\\\\n    \\midrule\n{body}\n"
        "    \\bottomrule\n  \\end{tabular}\n\\end{table}\n"
    )


def short(method: str) -> str:
    """jpamb.cases.Simple.divideByN:(I)I -> Simple.divideByN"""
    return method.split(":")[0].removeprefix("jpamb.cases.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", nargs="+", help="one or more CSV files from run_eval.py")
    ap.add_argument("--outdir", default="results")
    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    rows = [r for path in args.csv for r in csv.DictReader(open(path, newline=""))]
    modes = [m for m in MODE_ORDER if any(r["mode"] == m for r in rows)]
    modes += sorted({r["mode"] for r in rows} - set(modes))
    seeds = sorted({int(r["seed"]) for r in rows})

    # Methods no mode can run at all
    status = defaultdict(set)
    for r in rows:
        status[r["method"]].add(r["status"])
    excluded = sorted(m for m, s in status.items() if s <= FAILED_STATUS)
    rows = [r for r in rows if r["method"] not in excluded]

    # found[(mode, seed)][target] = first_exec or None
    found = defaultdict(dict)
    budget = 0
    for r in rows:
        if r["possible"] != "1":
            continue
        t = (r["method"], r["outcome"])
        found[(r["mode"], int(r["seed"]))][t] = int(r["first_exec"]) if r["found"] == "1" else None
        if r["total_execs"]:
            budget = max(budget, int(r["total_execs"]))

    targets = sorted({t for d in found.values() for t in d})
    failures = [t for t in targets if t[1] not in ("ok", "*")]
    out_md, out_tex = [], []

    # ---- Table 1: overall per mode --------------------------------------
    per_seed = {m: [sum(found[(m, s)].get(t) is not None for t in failures) for s in seeds] for m in modes}
    per_seed_all = {m: [sum(found[(m, s)].get(t) is not None for t in targets) for s in seeds] for m in modes}
    union = {m: sum(any(found[(m, s)].get(t) is not None for s in seeds) for t in failures) for m in modes}
    t1 = []
    for m in modes:
        f, a = per_seed[m], per_seed_all[m]
        sd = lambda xs: st.stdev(xs) if len(xs) > 1 else 0.0
        t1.append([m, f"{st.mean(f):.1f} ± {sd(f):.1f}", f"{union[m]}", f"{st.mean(a):.1f} ± {sd(a):.1f}"])
    h1 = ["Mode", f"Failures found per run (of {len(failures)})",
          f"Failures found in any run", f"Outcomes found per run (of {len(targets)})"]
    out_md.append("## Overall\n\n" + md_table(h1, t1))
    out_tex.append(tex_table(
        f"Failures found per mode ({len(seeds)} seeds, {budget} executions per run, "
        f"{len({t[0] for t in targets})} methods; mean $\\pm$ standard deviation).",
        "tab:overall", h1, t1))

    # ---- Table 2: pairwise statistics -----------------------------------
    t2 = []
    for x, y in [(b, a) for a, b in combinations(modes, 2)]:  # later (stronger) mode first
        A = a12(per_seed[x], per_seed[y])
        t2.append([f"{x} vs {y}", f"{st.mean(per_seed[x]) - st.mean(per_seed[y]):+.1f}",
                   fmt_p(mwu(per_seed[x], per_seed[y])), f"{A:.2f} ({effect(A)})"])
    h2 = ["Comparison", "Diff. in mean failures", "Mann-Whitney p", "A12"]
    out_md.append("## Failures found per run: pairwise tests\n\n" + md_table(h2, t2))
    out_tex.append(tex_table("Pairwise comparison of failures found per run.", "tab:stats", h2, t2))

    # ---- Table 3: failures where the modes differ -------------------------
    rate = {m: {t: sum(found[(m, s)].get(t) is not None for s in seeds) / len(seeds) for t in failures} for m in modes}
    t3 = []
    for t in failures:
        rs = [rate[m][t] for m in modes]
        if max(rs) - min(rs) > 0 or max(rs) == 0:
            t3.append([short(t[0]), t[1]] + [f"{int(round(r * 100))}%" for r in rs])
    t3.sort(key=lambda r: [-int(c[:-1]) for c in reversed(r[2:])])
    h3 = ["Method", "Failure"] + modes
    out_md.append("## Failures not found equally by all modes (share of runs that found it)\n\n"
                  + md_table(h3, t3))
    out_tex.append(tex_table("Detection rate per failure, for failures where the modes differ "
                             "or that no mode found.", "tab:perbug", h3, t3, "ll" + "r" * len(modes)))

    # ---- Table 4: speed on failures every mode finds ----------------------
    common = [t for t in failures if all(rate[m][t] == 1.0 for m in modes)]
    t4 = []
    for m in modes:
        meds = [st.median(found[(m, s)][t] for s in seeds) for t in common]
        t4.append([m, f"{st.median(meds):.0f}" if meds else "-", f"{st.mean(meds):.0f}" if meds else "-"])
    h4 = ["Mode", "Median executions to first find", "Mean of per-failure medians"]
    out_md.append(f"## Speed on the {len(common)} failures every mode always finds\n\n" + md_table(h4, t4))
    # per-failure speed tests (not found = budget + 1, i.e. censored)
    faster = []
    for x, y in [(b, a) for a, b in combinations(modes, 2)]:
        wins = losses = 0
        for t in failures:
            ex = [found[(x, s)].get(t) or budget + 1 for s in seeds]
            ey = [found[(y, s)].get(t) or budget + 1 for s in seeds]
            if mwu(ex, ey) < 0.05:
                if st.median(ex) < st.median(ey):
                    wins += 1
                else:
                    losses += 1
        faster.append([f"{x} vs {y}", wins, losses])
    hf = ["Comparison", "Failures found significantly faster", "Significantly slower"]
    out_md.append("Per failure, executions to first find (not found = budget), Mann-Whitney p < 0.05:\n\n"
                  + md_table(hf, faster))
    out_tex.append(tex_table("Speed: median executions to first find over the failures every mode "
                             "always finds.", "tab:speed", h4, t4))
    out_tex.append(tex_table("Number of failures one mode finds significantly faster (Mann-Whitney "
                             "$p<0.05$, not found counted as the full budget).", "tab:faster", hf, faster))

    if excluded:
        out_md.append(f"## Excluded ({len(excluded)} methods the interpreter cannot run)\n\n"
                      + ", ".join(short(m) for m in excluded))

    text = "\n\n".join(out_md)
    print(text)
    (outdir / "summary.md").write_text(text + "\n", encoding="utf-8")
    (outdir / "tables.tex").write_text("% generated by summarize.py\n" + "\n".join(out_tex), encoding="utf-8")

    # ---- Plot: failures found vs executions ------------------------------
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n(matplotlib not installed: no plot. Use --group eval.)")
        return
    xs = sorted({1, budget} | {int(round(10 ** (k / 20))) for k in range(0, 200) if 10 ** (k / 20) <= budget})
    fig, ax = plt.subplots(figsize=(4.5, 2.8))
    for m, style in zip(modes, ["-", "--", "-.", ":"]):
        mean = [st.mean(sum(1 for t in failures if (e := found[(m, s)].get(t)) is not None and e <= x)
                        for s in seeds) for x in xs]
        ax.step(xs, mean, style, where="post", label=m)
    ax.set_xscale("log")
    ax.set_xlabel("Executions")
    ax.set_ylabel(f"Failures found (of {len(failures)})")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "progress.pdf")
    fig.savefig(outdir / "progress.png", dpi=200)
    print(f"\nWrote {outdir / 'summary.md'}, {outdir / 'tables.tex'}, {outdir / 'progress.pdf'}")


if __name__ == "__main__":
    main()
