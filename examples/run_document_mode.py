"""Mode document (§7ter, v4) : analyse / synthèse / production.

Démontre sur une loi fictive de 3 articles :
- INV-015 : la mosaïque des statuts, jamais de statut agrégé ;
- INV-016 : plancher de risque élevé en production et en synthèse de normatif ;
- INV-017 / piège B5 : l'omission silencieuse d'un article bloque la synthèse,
  la même omission DÉCLARÉE la rend publiable (déléguée à l'humain).
Aucun LLM, aucun réseau : tout est déterministe.
"""
import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root / "src"))

from sentinel_guard.document import segment_source_units, verify_document
from sentinel_guard.types import Claim, ClaimStatus, CoverageMap, DocumentDraft, DocumentMode, Passage

LOI = Passage(
    source_id="LOI-DEMO",
    source_type="normatif",
    opposable=True,
    text=(
        "Article 1er\n"
        "Le délai de rétractation est de dix jours.\n"
        "\n"
        "Article 2\n"
        "La sanction du non-respect est la nullité du contrat.\n"
        "\n"
        "Article 3\n"
        "Les modalités d'application sont fixées par décret.\n"
    ),
    metadata={"etat": "VIGUEUR"},
)

CITATION = "Le délai de rétractation est de dix jours."


def show(title: str, draft: DocumentDraft) -> None:
    result = verify_document(draft, LOI)
    print(f"--- {title} (mode {result.mode.value}) ---")
    for c in result.verification.claims:
        print(f"  [{c.status.value}] « {c.ref} »")
    print(f"  risque : {result.risk_tier.value} · publiable : {result.publishable}")
    for v in result.coverage_violations:
        # marqueur ASCII : la console Windows (cp1252) ne connaît pas "⚠"
        print(f"  [!] {v}")
    print()


def main() -> None:
    print(f"Unités segmentées par le code : {segment_source_units(LOI.text)}")
    print()

    # ANALYSE : citation exacte + interprétation ancrée -> mosaïque de statuts (INV-015).
    show(
        "Analyse du texte",
        DocumentDraft(
            mode=DocumentMode.ANALYSE,
            claims=(
                Claim(ref=CITATION, status=ClaimStatus.AUTHENTIFIÉ),
                Claim(ref="Un décret fixera les modalités d'application du délai.", status=ClaimStatus.INTERPRÉTATION),
            ),
        ),
    )

    # PRODUCTION : même un verbatim parfait reste à risque élevé (INV-016).
    show(
        "Production d'un amendement",
        DocumentDraft(mode=DocumentMode.PRODUCTION, claims=(Claim(ref=CITATION, status=ClaimStatus.AUTHENTIFIÉ),)),
    )

    # SYNTHÈSE, piège B5 : l'article 3 disparaît sans être déclaré omis -> blocage.
    show(
        "Synthèse à trou (B5)",
        DocumentDraft(
            mode=DocumentMode.SYNTHÈSE,
            claims=(Claim(ref=CITATION, status=ClaimStatus.AUTHENTIFIÉ),),
            coverage=CoverageMap(
                source_units=("Article 1er", "Article 2", "Article 3"),
                covered={"Article 1er": (CITATION,), "Article 2": (CITATION,)},
                omitted=(),
            ),
        ),
    )

    # SYNTHÈSE conforme : la même omission, DÉCLARÉE -> publiable (risque élevé, normatif).
    show(
        "Synthèse avec omission déclarée",
        DocumentDraft(
            mode=DocumentMode.SYNTHÈSE,
            claims=(Claim(ref=CITATION, status=ClaimStatus.AUTHENTIFIÉ),),
            coverage=CoverageMap(
                source_units=("Article 1er", "Article 2", "Article 3"),
                covered={"Article 1er": (CITATION,), "Article 2": (CITATION,)},
                omitted=("Article 3",),
            ),
        ),
    )


if __name__ == "__main__":
    main()
