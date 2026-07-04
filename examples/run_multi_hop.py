import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root / "src"))

from sentinel_guard._3_retrieval.moulineuse import MoulineuseRetrievalProvider
from sentinel_guard._3_retrieval.multi_hop import build_hop_query, extract_followable_hops
from sentinel_guard._3_retrieval.retrieval import advance_retrieval
from sentinel_guard.core_types.types import Intent, RetrievalState


def main() -> None:
    # §4ter : multi-saut réel borné par du code (max_hops, visited_documents),
    # jamais par le modèle. Article 1103 du Code civil -> renvoi CITATION réel
    # vers l'article L422-2-1 du Code de la construction et de l'habitation.
    provider = MoulineuseRetrievalProvider()
    intent = Intent(id="1", question="Que dit l'article 1103 du Code civil ?")
    state = RetrievalState(hop_count=0, visited_documents=set(), remaining_budget=5)

    passage1, state = advance_retrieval(
        intent, provider, {"route": "code_article", "article": "1103", "code": "code civil"}, state, max_hops=3
    )
    print(f"Saut 1 : {passage1.source_id} (hop_count={state.hop_count})")

    hops = extract_followable_hops(passage1)
    print(f"{len(hops)} renvois suivables (CITATION/CONCORDANCE vers un CODE) :")
    for hop in hops:
        print(f"  - art. {hop.article_num} : {hop.description}")

    target = next((h for h in hops if "construction" in h.description.lower()), None)
    if target is None:
        print("Aucun renvoi pertinent -> arrêt (§4ter, jamais de rapprochement opportuniste)")
        return

    query2 = build_hop_query(target, code_title_hint="construction et de l'habitation")
    passage2, state = advance_retrieval(intent, provider, query2, state, max_hops=3)

    print(f"\nSaut 2 : {passage2.source_id} (hop_count={state.hop_count})")
    print(f"visited_documents={state.visited_documents}")
    print(f"texte (extrait) : {passage2.text[:150]}...")


if __name__ == "__main__":
    main()
