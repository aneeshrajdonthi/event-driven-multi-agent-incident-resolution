"""API Gateway Service - routes requests to downstream microservices."""
import asyncio
from typing import Dict, Any

class GatewayService:
    def __init__(self):
        self.downstream_timeout_sec = 30.0

    async def route_request(self, path: str, method: str, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
        """Routes inbound HTTP requests.
        
        BUG: Missing circuit breaker and short timeouts during cascading failures cause 502/504 storms.
        """
        if path.startswith("/api/orders"):
            # Cascading timeout failure
            await asyncio.sleep(5.0)
            return {"status_code": 504, "body": {"error": "Gateway Timeout"}}
        
        return {"status_code": 200, "body": {"message": "Success"}}
