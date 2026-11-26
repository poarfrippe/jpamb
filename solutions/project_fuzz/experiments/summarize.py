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
    n_methods = len({t[0] for t in targets})
    out_md, out_tex = [], []
    sd = lambda xs: st.stdev(xs) if len(xs) > 1 else 0.0
    pairs = [(b, a) for a, b in combinations(modes, 2)]  # later (stronger) mode first

    per_seed = {m: [sum(found[(m, s)].get(t) is not None for t in failures) for s in seeds] for m in modes}
    union = {m: sum(any(found[(m, s)].get(t) is not None for s in seeds) for t in failures) for m in modes}
    rate = {m: {t: sum(found[(m, s)].get(t) is not None for s in seeds) / len(seeds) for t in failures}
            for m in modes}
    stats = {}
    for x, y in pairs:
        stats[(x, y)] = (st.mean(per_seed[x]) - st.mean(per_seed[y]),
                         mwu(per_seed[x], per_seed[y]), a12(per_seed[x], per_seed[y]))

    # Group the bugs: found by exactly one mode / by nobody / by several but not every run
    only = {m: [] for m in modes}
    nobody, unreliable = [], []
    for t in failures:
        finders = [m for m in modes if rate[m][t] > 0]
        if not finders:
            nobody.append(t)
        elif len(finders) == 1 and len(modes) > 1:
            only[finders[0]].append(t)
        elif any(rate[m][t] < 1 for m in modes):
            unreliable.append(t)
    always_all = [t for t in failures if all(rate[m][t] == 1.0 for m in modes)]
    name = lambda t: f"{short(t[0])} ({t[1]})"

    # ---- Header and plain-language summary --------------------------------
    out_md.append(
        "# Evaluation summary\n\n"
        f"Setup: {n_methods} benchmark methods compared, {len(seeds)} runs (seeds) per mode, "
        f"about {round(budget, -2):.0f} inputs per run. A \"bug\" here is any outcome other than ok, "
        f"so there are {len(failures)} bugs to find in total."
        + (f" {len(excluded)} methods the interpreter cannot run are left out (see the end)." if excluded else ""))

    lines = []
    ranking = sorted(modes, key=lambda m: -st.mean(per_seed[m]))
    lines.append("- Bugs found per run, on average: "
                 + ", ".join(f"**{m}** {st.mean(per_seed[m]):.1f}" for m in ranking)
                 + f" (out of {len(failures)}).")
    for (x, y), (diff, p, A) in stats.items():
        more = "more" if diff >= 0 else "fewer"
        real = ("this difference is **real** (p = " + fmt_p(p) + ")") if p < 0.05 else \
               ("this difference is **not proven** yet (p = " + fmt_p(p) + ", needs p < 0.05)")
        favour = x if A >= 0.5 else y
        lines.append(f"- **{x} vs {y}**: {x} finds {abs(diff):.1f} {more} bugs per run; {real}. "
                     f"A run of {x} beats a run of {y} {A * 100:.0f}% of the time "
                     f"({effect(A)} effect" + (f" in favour of {favour})." if effect(A) != "negligible" else ")."))
    for m in modes:
        if only[m]:
            lines.append(f"- **{len(only[m])} bug{'s are' if len(only[m]) != 1 else ' is'} only found by {m}**: "
                         + ", ".join(name(t) for t in only[m]) + ".")
    if nobody:
        lines.append(f"- **{len(nobody)} bug{'s are' if len(nobody) != 1 else ' is'} found by no mode**: " + ", ".join(name(t) for t in nobody) + ".")
    lines.append(f"- {len(always_all)} bugs are easy: every mode finds them in every run.")
    if len(seeds) < 5:
        lines.append(f"- Note: with only {len(seeds)} runs per mode no difference can be proven "
                     "statistically. Use --seeds 10 for the real results.")
    out_md.append("## In short\n\n" + "\n".join(lines))

    # ---- Table 1: bugs found per mode ----------------------------------------
    t1 = [[m, f"{st.mean(per_seed[m]):.1f} ± {sd(per_seed[m]):.1f}", union[m]] for m in modes]
    h1 = ["Mode", f"Bugs found per run (of {len(failures)})", "Bugs found in at least one run"]
    out_md.append("## 1. Bugs found per mode\n\n" + md_table(h1, t1) +
                  "\n\nAverage over all runs; ± is how much the runs vary. "
                  "The last column counts every bug the mode found at least once.")
    out_tex.append(tex_table(
        f"Bugs found per mode ({len(seeds)} seeds, about {round(budget, -2):.0f} executions per run, "
        f"{n_methods} methods, {len(failures)} possible failures; mean $\\pm$ standard deviation).",
        "tab:overall", h1, t1))

    # ---- Table 2: is the difference real? ----------------------------------
    t2 = [[f"{x} vs {y}", f"{diff:+.1f}", fmt_p(p), "yes" if p < 0.05 else "no",
           f"{A:.2f} ({effect(A)})"] for (x, y), (diff, p, A) in stats.items()]
    h2 = ["Comparison", "Difference in bugs per run", "p (Mann-Whitney)", "Real difference? (p < 0.05)",
          "A12: chance first mode wins"]
    out_md.append("## 2. Is the difference real?\n\n" + md_table(h2, t2) +
                  "\n\np = chance of seeing this difference if both modes were equally good; "
                  "below 0.05 counts as real. A12 = how often a run of the first mode beats a run of the "
                  "second (0.5 = no difference, 1.0 = always; from 0.71 a large effect).")
    out_tex.append(tex_table("Pairwise comparison of bugs found per run: Mann-Whitney U test and "
                             "Vargha-Delaney A12 effect size.", "tab:stats", h2, t2))

    # ---- Table 3: which bugs differ ------------------------------------------
    pct = lambda t: [f"{int(round(rate[m][t] * 100))}%" for m in modes]
    h3 = ["Method", "Bug"] + modes
    parts = ["## 3. Which bugs make the difference\n\n"
             "Percentages = share of runs that found the bug. Bugs every mode always finds are not listed."]
    for m in modes:
        if only[m]:
            parts.append(f"### Only found by {m}\n\n" + md_table(h3, [[short(t[0]), t[1]] + pct(t) for t in only[m]]))
    if unreliable:
        rows3 = sorted(unreliable, key=lambda t: [-rate[m][t] for m in reversed(modes)])
        parts.append("### Found by several modes, but not in every run\n\n"
                     + md_table(h3, [[short(t[0]), t[1]] + pct(t) for t in rows3]))
    if nobody:
        parts.append("### Found by no mode\n\n" + md_table(["Method", "Bug"], [[short(t[0]), t[1]] for t in nobody]))
    out_md.append("\n\n".join(parts))
    t3 = [[short(t[0]), t[1]] + pct(t) for m in modes for t in only[m]] + \
         [[short(t[0]), t[1]] + pct(t) for t in unreliable] + [[short(t[0]), t[1]] + pct(t) for t in nobody]
    out_tex.append(tex_table("Detection rate per bug (share of runs that found it), for bugs where the "
                             "modes differ or that no mode found.", "tab:perbug", h3, t3, "ll" + "r" * len(modes)))

    # ---- Table 4: speed -------------------------------------------------------
    t4 = []
    for m in modes:
        meds = [st.median(found[(m, s)][t] for s in seeds) for t in always_all]
        t4.append([m, f"{st.mean(meds):.0f}" if meds else "-"])
    faster = []
    for x, y in pairs:
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
    h4 = ["Mode", f"Average inputs needed (over the {len(always_all)} easy bugs)"]
    hf = ["Comparison", "Bugs the first mode finds significantly faster", "Significantly slower"]
    out_md.append("## 4. Speed\n\n" + md_table(h4, t4) +
                  "\n\nHow many inputs a mode needs before it finds a bug, for the bugs every mode always finds "
                  "(lower = faster).\n\n" + md_table(hf, faster) +
                  "\n\nPer bug: is one mode clearly faster (Mann-Whitney p < 0.05; a bug that is never found "
                  "counts as needing the whole budget)?")
    out_tex.append(tex_table("Speed: mean number of executions until first found, over the bugs every "
                             "mode always finds.", "tab:speed", h4, t4))
    out_tex.append(tex_table("Number of bugs one mode finds significantly faster (Mann-Whitney "
                             "$p<0.05$, not found counted as the full budget).", "tab:faster", hf, faster))

    if excluded:
        out_md.append(f"## Left out: {len(excluded)} methods the interpreter cannot run\n\n"
                      "No mode can find anything in these (unsupported instructions, String methods or "
                      "parameter types), so they are not part of the comparison:\n\n"
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
