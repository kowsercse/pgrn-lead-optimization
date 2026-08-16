"""Command line entry point: `dossier run --target <SYMBOL>`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

from .pipeline import Evidence, run_pipeline
from .scouts.assays import AssaysScout
from .scouts.bioactivity import BioactivityScout
from .scouts.literature import LiteratureScout
from .scouts.patents import PatentsScout
from .scouts.structures import StructuresScout
from .store import connect, new_run

SCOUTS = (StructuresScout(), BioactivityScout(), PatentsScout(),
          AssaysScout(), LiteratureScout())


def http_fetch(source_id: str) -> str | None:
    """Resolve an identifier at its home database."""
    sid = source_id.strip()
    if sid.upper().startswith("CHEMBL"):
        url = f"https://www.ebi.ac.uk/chembl/api/data/target/{sid}.json"
    elif sid.isdigit() and len(sid) > 4:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/{sid}/description/JSON"
    elif sid.isdigit():
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={sid}&retmode=json"
    else:
        url = f"https://data.rcsb.org/rest/v1/core/entry/{sid}"
    try:
        r = requests.get(url, timeout=30)
    except requests.RequestException:
        return None
    return r.text if r.ok else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dossier")
    ap.add_argument("command", choices=["run"])
    ap.add_argument("--target", required=True)
    ap.add_argument("--db", default="dossier.db")
    ap.add_argument("--out", default="dossiers")
    args = ap.parse_args(argv)

    conn = connect(args.db)
    run_id = new_run(conn, target=args.target)
    print(f"run {run_id[:8]} target {args.target}", file=sys.stderr)

    result = run_pipeline(conn, target=args.target, scouts=SCOUTS,
                          fetch=http_fetch, evidence=None,
                          out_dir=Path(args.out), run_id=run_id)

    print(f"  verdict:  {result.verdict or 'retrieval complete'}", file=sys.stderr)
    print(f"  gaps:     {len(result.gaps)}", file=sys.stderr)
    print(f"  demoted:  {len(result.demoted)}", file=sys.stderr)
    print(result.dossier_v1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
