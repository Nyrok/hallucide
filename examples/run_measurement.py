import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root / "src"))

from hallucide.analysis.measurement import run_document_measurement, run_measurement, run_triage_measurement
from hallucide.analysis.trap_dataset import DOCUMENT_TRAP_DATASET, TRAP_DATASET, TRIAGE_DATASET


def main() -> None:
    report = run_measurement(TRAP_DATASET)
    print(f"=== Banc de mesure §12 ({report.total_cases} cas) ===")
    print(f"Taux de blocage correct : {report.correct_blocking_rate:.0%}")
    print(f"Taux de sur-refus        : {report.over_refusal_rate:.0%}")
    print()
    print("Métriques par type de piège :")
    for m in report.metrics_by_trap_type:
        print(f"  {m.trap_type:<14} {m.correct}/{m.total}  ({m.accuracy:.0%})")

    print()
    triage_report = run_triage_measurement(TRIAGE_DATASET)
    print(f"=== Triage ({triage_report.total} cas) ===")
    print(f"Taux de faux négatifs : {triage_report.false_negative_rate:.0%}")

    print()
    doc_report = run_document_measurement(DOCUMENT_TRAP_DATASET)
    print(f"=== Mode document, §12 v4 ({len(doc_report.results)} cas) ===")
    print("Sur-refus par mode      :", {m: f"{r:.0%}" for m, r in doc_report.over_refusal_rate_by_mode.items()})
    print("Blocage correct par mode:", {m: f"{r:.0%}" for m, r in doc_report.correct_blocking_rate_by_mode.items()})
    doc_failures = [r for r in doc_report.results if not r.correct]
    for r in doc_failures:
        print(f"  ECHEC {r.case.id}: publiable={r.publishable}, attendu={'publiable' if r.case.is_answerable else 'bloque'}")

    failures = [r for r in report.results if not r.correct]
    if failures:
        print()
        print("Échecs détaillés :")
        for r in failures:
            print(f"  {r.case.id}: attendu={r.case.expected_status} obtenu={r.actual_status}")


if __name__ == "__main__":
    main()
