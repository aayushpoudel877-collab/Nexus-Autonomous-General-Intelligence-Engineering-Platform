"""Run a small local retrieval demo without external services or API keys."""
from .chunking import chunk_text
from .retrieval import hybrid_retrieve, pack_evidence
from .grounding import evidence_prompt_block, validate_citations

def main() -> None:
    docs = {
        "nexus-overview": ("NEXUS platform overview", "NEXUS-Ω combines AI engineering workflows, learning services, model evaluation, and operator oversight."),
        "rag-safety": ("RAG safety notes", "Retrieval augmented generation should cite evidence, scope documents by tenant, and treat retrieved text as untrusted data."),
    }
    chunks = []
    for doc_id, (_, content) in docs.items():
        chunks.extend(chunk_text(content, doc_id, "demo-tenant", max_chars=180, overlap=20))
    hits = hybrid_retrieve("How should RAG handle retrieved evidence safely?", chunks, tenant_id="demo-tenant", top_k=3)
    evidence = pack_evidence(hits, {key: title for key, (title, _) in docs.items()})
    print(evidence_prompt_block(evidence))
    answer = "RAG should scope retrieval to the tenant and treat retrieved text as untrusted data [E1]."
    print("\\nCitation check:", validate_citations(answer, evidence))

if __name__ == "__main__":
    main()
