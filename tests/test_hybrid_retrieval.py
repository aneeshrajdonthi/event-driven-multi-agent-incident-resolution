"""Unit and integration tests for hybrid retrieval (Qdrant + BM25 + Cross-Encoder)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.retrieval.hybrid import HybridRetriever, RetrievalResult, _reciprocal_rank_fusion
from src.retrieval.bm25_index import BM25Index


def test_reciprocal_rank_fusion():
    """Verify RRF correctly scores and ranks documents across multiple lists."""
    list1 = ["doc_a", "doc_b", "doc_c"]
    list2 = ["doc_b", "doc_a", "doc_d"]
    
    fused = _reciprocal_rank_fusion(list1, list2, k=60)
    docs = [doc for doc, _ in fused]
    
    # doc_a and doc_b appear in both, so should be top 2
    assert "doc_a" in docs[:2]
    assert "doc_b" in docs[:2]
    assert docs.index("doc_d") > 1


def test_bm25_index():
    """Test BM25 index building and searching."""
    index = BM25Index()
    docs = [
        "payment gateway timeout error connection pool full",
        "cpu utilization high order service",
        "memory leak in worker process"
    ]
    index.build_index(docs)
    
    results = index.search("timeout connection", top_k=2)
    assert len(results) > 0
    # First doc should match top
    top_doc_id, top_score = results[0]
    assert top_doc_id == 0
    assert top_score > 0.0


@pytest.mark.asyncio
async def test_hybrid_retriever_pipeline():
    """Test end-to-end hybrid retrieve with mocked components."""
    mock_vector_store = MagicMock()
    mock_vector_store.search = AsyncMock(return_value=[
        {"content": "Database pool exhausted", "score": 0.88, "metadata": {"file": "payment_service.py"}},
        {"content": "Order processing loop", "score": 0.75, "metadata": {"file": "order_service.py"}}
    ])
    
    mock_bm25 = MagicMock()
    mock_bm25.documents = [
        "Database pool exhausted",
        "Order processing loop",
        "Garbage collection high pause"
    ]
    mock_bm25.search = MagicMock(return_value=[(0, 1.5), (2, 0.8)])
    
    mock_reranker = MagicMock()
    mock_reranker.rerank = MagicMock(return_value=[
        ("Database pool exhausted", 0.95),
        ("Order processing loop", 0.60)
    ])
    
    retriever = HybridRetriever(
        vector_store=mock_vector_store,
        bm25_index=mock_bm25,
        reranker=mock_reranker
    )
    
    results = await retriever.retrieve("database connection timeout", top_k=2)
    assert len(results) == 2
    assert isinstance(results[0], RetrievalResult)
    assert results[0].content == "Database pool exhausted"
    assert results[0].score == 0.95
