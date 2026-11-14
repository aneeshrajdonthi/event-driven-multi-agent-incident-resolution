"""Payment Service - handles payments and transactions."""
import asyncio
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Global cache without TTL or eviction causing memory leak
TRANSACTION_AUDIT_LOG: List[Dict[str, Any]] = []

class PaymentService:
    def __init__(self, db_pool=None):
        self.db_pool = db_pool

    async def charge(self, account_id: str, amount_cents: int, idempotency_key: str) -> Dict[str, Any]:
        """Processes payment charge.
        
        BUG 1: Connection pool leak — acquires connection without context manager/release on error.
        BUG 2: Memory leak — TRANSACTION_AUDIT_LOG retains raw payload indefinitely.
        """
        # Connection acquired without proper try...finally release
        conn = await self._acquire_connection()
        
        try:
            # Simulate transaction processing
            result = {
                "transaction_id": f"txn_{idempotency_key}",
                "account_id": account_id,
                "amount": amount_cents,
                "status": "SUCCESS"
            }
            # Unbounded memory growth:
            TRANSACTION_AUDIT_LOG.append({
                "key": idempotency_key,
                "details": "x" * 1024 * 50,  # 50KB retained per txn
                "result": result
            })
            return result
        except Exception as e:
            logger.error(f"Payment failed: {e}")
            raise
        # Missing conn.release() in finally block causes connection pool exhaustion!

    async def _acquire_connection(self):
        # Simulates pool acquisition
        return {"id": "mock_conn"}
