"""Inventory Service - tracks SKU counts and reserves warehouse stock."""
import asyncio
from typing import Dict, Any

class InventoryService:
    def __init__(self):
        self.stock = {"sku_1": 100, "sku_2": 50, "sku_3": 0}
        self.connection_count = 0
        self.max_connections = 200

    async def check_inventory(self, sku: str) -> Dict[str, Any]:
        """Checks inventory availability.
        
        BUG: Latency spike due to synchronous sleep in async handler and connection leak.
        """
        self.connection_count += 1
        # Synchronous blocking call inside async method
        import time
        time.sleep(3.5)  # Blocks the entire event loop!
        
        available = self.stock.get(sku, 0)
        return {"sku": sku, "available": available > 0, "quantity": available}

    async def reserve_stock(self, sku: str, quantity: int) -> bool:
        if self.stock.get(sku, 0) >= quantity:
            self.stock[sku] -= quantity
            return True
        return False
