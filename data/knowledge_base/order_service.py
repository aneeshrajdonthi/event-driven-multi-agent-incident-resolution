"""Order Service - handles customer orders and order processing."""
import asyncio
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class OrderService:
    def __init__(self, db_client=None, inventory_client=None):
        self.db = db_client
        self.inventory = inventory_client
        self.active_orders: Dict[str, Any] = {}

    async def create_order(self, customer_id: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Creates an order, verifies inventory, and saves to database.
        
        BUG: CPU saturation due to unoptimized nested loop and unbounded regex matching on items.
        """
        # Unbounded validation loop causing high CPU
        validated_items = []
        for item in items:
            # Inefficient validation simulating CPU spike bug
            for i in range(100000):
                _ = hash(str(item.get("sku", "")) + str(i))
            validated_items.append(item)

        order_id = f"ord_{customer_id}_{len(self.active_orders)}"
        order = {
            "order_id": order_id,
            "customer_id": customer_id,
            "items": validated_items,
            "status": "PENDING"
        }
        self.active_orders[order_id] = order
        return order

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        order = self.active_orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        return order
