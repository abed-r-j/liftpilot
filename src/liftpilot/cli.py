"""Command line: ``liftpilot download | train | report | results | agent | agent-eval | app``."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from liftpilot import config

app = typer.Typer(add_completion=False, help="LiftPilot: profit-optimal campaign targeting.")
console = Console()

CHECKSUMS = "data/checksums.sha256"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@app.command()
def download(dataset: str = typer.Argument("all", help="x5, hillstrom or all")) -> None:
    """Download the public datasets and verify their SHA-256 checksums."""
    import httpx

    from liftpilot.data import prepare, x5

    todo: list[tuple[str, str, str]] = []
    if dataset in ("x5", "all"):
        todo += [("x5", f, f"{x5.BASE_URL}/{f}") for f in x5.RAW_FILES]
    if dataset in ("hillstrom", "all"):
        todo.append(("hillstrom", "hillstrom.csv", prepare.HILLSTROM_URL))
    known = {}
    manifest = config.root() / CHECKSUMS
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            digest, name = line.split(maxsplit=1)
            known[name.strip()] = digest
    for ds, name, url in todo:
        target = config.raw_dir(ds) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            console.print(f"downloading {url}")
            with httpx.stream(
                "GET", url, follow_redirects=True, timeout=httpx.Timeout(30.0, read=600.0)
            ) as r:
                r.raise_for_status()
                with target.open("wb") as fh:
                    for chunk in r.iter_bytes(1 << 20):
                        fh.write(chunk)
        digest = _sha256(target)
        key = f"{ds}/{name}"
        if key in known and known[key] != digest:
            raise typer.BadParameter(f"checksum mismatch for {key}: delete the file and retry")
        console.print(f"[green]ok[/green] {key}  sha256={digest[:16]}...")


@app.command()
def train(
    dataset: str = typer.Argument("x5", help="x5 or hillstrom"),
    seed: int = 0,
    n_boot: int = 300,
    repeats: int = 5,
    rebuild: bool = typer.Option(False, help="rebuild the customer table from raw files"),
) -> None:
    """Build features, train and evaluate every learner, write artifacts/."""
    from liftpilot import pipeline
    from liftpilot.data import prepare

    if dataset == "x5":
        exp = prepare.load_x5(
            config.raw_dir("x5"), config.interim_dir(), seed=seed, rebuild=rebuild
        )
        ablation = {
            "RFM only (3 features)": ["recency_days", "frequency", "monetary"],
            "All behaviour features": exp.features,
        }
        exp.frame["age_filled"] = exp.frame["age"].fillna(-1.0)
        exp.frame["gender_female"] = (exp.frame["gender"] == "female").astype(float)
        exp.frame["gender_male"] = (exp.frame["gender"] == "male").astype(float)
        ablation["Behaviour + age and gender"] = [
            *exp.features,
            "age_filled",
            "gender_female",
            "gender_male",
        ]
    elif dataset == "hillstrom":
        exp = prepare.load_hillstrom(config.raw_dir("hillstrom"), seed=seed)
        ablation = None
    else:
        raise typer.BadParameter("dataset must be x5 or hillstrom")
    report = pipeline.run(
        exp,
        config.artifacts_dir(dataset),
        seed=seed,
        n_boot=n_boot,
        repeats=repeats,
        extra_feature_sets=ablation,
    )
    show(report)


def show(report: dict) -> None:
    ro = report["experiment_readout"]
    console.print(
        f"[bold]{report['dataset']['name']}[/bold]: control {ro['rate_control']:.2%}, "
        f"treated {ro['rate_treated']:.2%}, uplift {ro['ate']:+.2%} (p={ro['p_value']:.2g})"
    )
    tab = Table(
        "learner", "Qini cal", "Qini test [95% CI]", "uplift@10%", "uplift@30%", "repeat mean±sd"
    )
    for name, row in report["learners"].items():
        q = row["qini_test"]
        rep = report.get("learners_repeated", {}).get(name)
        tab.add_row(
            name + (" *" if name == report["champion"] else ""),
            f"{row['qini_calibration']:.4f}",
            f"{q['value']:.4f} [{q['ci_low']:.4f}, {q['ci_high']:.4f}]",
            f"{row['uplift_at_10']:+.3f}",
            f"{row['uplift_at_30']:+.3f}",
            f"{rep['mean']:.4f}±{rep['sd']:.4f}" if rep else "-",
        )
    console.print(tab)
    cur = report["economics"]["currency"]
    tab = Table(
        "policy", "contacted", f"spend {cur}", f"incr. profit {cur} [95% CI]", "P(>0)", "iROAS"
    )
    for name, p in report["policies"].items():
        tab.add_row(
            name,
            f"{p['share_selected']:.1%}",
            f"{p['spend']:,.0f}",
            f"{p['incremental_profit']:,.0f} [{p['profit_ci_low']:,.0f}, {p['profit_ci_high']:,.0f}]",
            f"{p['prob_profit_positive']:.0%}",
            f"{p['incremental_roas']:.2f}" if p["incremental_roas"] is not None else "-",
        )
    console.print(tab)
    console.print("types:", {k: f"{v['share']:.1%}" for k, v in report["types"].items()})


@app.command()
def report(dataset: str = typer.Argument("x5")) -> None:
    """Print the saved evaluation report."""
    path = config.artifacts_dir(dataset) / "report.json"
    show(json.loads(path.read_text()))


@app.command()
def agent(
    request: str = typer.Argument(..., help="what you want the agent to do, in plain words"),
    dataset: str = "x5",
    scripted: bool = typer.Option(False, help="skip the language model; fixed tool order"),
    offline: bool = typer.Option(False, help="use cached live data"),
    show_results: bool = typer.Option(False, help="print each tool result"),
) -> None:
    """Run the campaign agent once and print its answer and tool trace."""
    from liftpilot.agent.runtime import build_agent

    ag = build_agent(dataset, use_llm=not scripted, offline=offline)
    run = ag.run_scripted(request) if scripted else ag.run(request)
    for i, s in enumerate(run.steps, 1):
        err = " [red]ERROR[/red]" if isinstance(s.result, dict) and "error" in s.result else ""
        console.print(f"[dim]{i:2d}. {s.tool}({json.dumps(s.args)}) {s.seconds:.2f}s[/dim]{err}")
        if show_results or err:
            console.print(f"[dim]    {json.dumps(s.result, default=str)[:700]}[/dim]")
    console.rule(f"answer ({run.mode}, {run.seconds:.0f}s)")
    console.print(run.answer, markup=False)
    g = run.grounding
    if g:
        console.rule()
        console.print(
            f"numeric grounding: {g.grounded}/{g.checked}"
            + (f"  ungrounded: {g.ungrounded}" if g.ungrounded else "")
        )
    if run.rejected_narrative:
        console.print(
            "[yellow]model narrative rejected by the guards; verified statements "
            "shown instead[/yellow]"
        )
    if run.pending_approval:
        console.print(f"[yellow]waiting for human approval of {run.pending_approval}[/yellow]")


@app.command()
def results(offline: bool = False) -> None:
    """Run the extra analyses and regenerate docs/RESULTS.md and docs/figures/."""
    from liftpilot import figures
    from liftpilot import results as res

    res.extra_analyses("x5", offline=offline)
    path = res.write_results_md()
    names = figures.make_all()
    console.print(f"wrote {path} and {len(names)} figures")


@app.command(name="agent-eval")
def agent_eval(dataset: str = "x5", offline: bool = False) -> None:
    """Benchmark the agent on fixed requests; writes artifacts/agent_eval.json."""
    from liftpilot.agent.evaluate import run_benchmark
    from liftpilot.agent.runtime import build_agent

    ag = build_agent(dataset, use_llm=True, offline=offline)
    res = run_benchmark(ag, config.root() / "artifacts" / "agent_eval.json")
    for r in res["runs"]:
        console.print(json.dumps(r, default=str), markup=False)
    console.rule("summary")
    console.print(json.dumps(res["summary"], indent=2), markup=False)


@app.command(name="app")
def run_app(port: int = 8501) -> None:
    """Start the demo dashboard."""
    script = Path(__file__).parent / "app" / "main.py"
    subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(script),
            "--server.port",
            str(port),
            "--browser.gatherUsageStats",
            "false",
        ],
        check=False,
    )


if __name__ == "__main__":
    app()
