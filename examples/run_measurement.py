import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root / "src"))

from sentinel_guard.measurement import run_measurement, run_triage_measurement
from sentinel_guard.trap_dataset import TRAP_DATASET, TRIAGE_DATASET


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

    failures = [r for r in report.results if not r.correct]
    if failures:
        print()
        print("Échecs détaillés :")
        for r in failures:
            print(f"  {r.case.id}: attendu={r.case.expected_status} obtenu={r.actual_status}")


if __name__ == "__main__":
    main()
