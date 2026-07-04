import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root / "src"))

from sentinel_guard.analysis.calibration import Annotation, run_calibration
from sentinel_guard.analysis.measurement import REFUS
from sentinel_guard.analysis.trap_dataset import TRAP_DATASET


def main() -> None:
    # §12 : la calibration valide le jeu de test (trap_dataset.py), pas une
    # exécution du système. Ici, deux annotateurs relisent un sous-ensemble
    # des cas et disent quel statut ils attribueraient -- sans voir le
    # expected_status déjà figé dans le dataset.
    sample = TRAP_DATASET[:7]

    annotations = []
    for case in sample:
        expected = case.expected_status.value if case.expected_status is not None else REFUS

        # Annotateur 1 : d'accord avec le gold standard sur tous les cas.
        annotations.append(Annotation(case_id=case.id, annotator_id="annotateur_1", judged_status=expected))

        # Annotateur 2 : d'accord sauf sur un cas ambigu (simule un vrai
        # désaccord humain plausible, ex. hésitation entre INTERPRÉTATION
        # et CITÉ_NON_OPPOSABLE sur un cas limite).
        judged = "INTERPRÉTATION" if case.id == "f1-verbatim-non-opposable" else expected
        annotations.append(Annotation(case_id=case.id, annotator_id="annotateur_2", judged_status=judged))

    report = run_calibration(annotations)

    print(f"=== Calibration inter-annotateur (§12, {len(sample)} cas, dont 1 désaccord simulé) ===")
    for annotator_a, annotator_b, kappa_result in report.pairwise_kappas:
        print(f"{annotator_a} vs {annotator_b} : kappa={kappa_result.kappa:.2f} "
              f"(accord observé {kappa_result.agreement_count}/{kappa_result.total_count})")
    print(f"Kappa moyen : {report.mean_kappa:.2f}")


if __name__ == "__main__":
    main()
