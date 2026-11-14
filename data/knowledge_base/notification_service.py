"""Notification Service - dispatches push notifications and emails."""
import asyncio
from typing import Dict, Any

class NotificationService:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def send_notification(self, user_id: str, message: str, channel: str = "email") -> bool:
        """Sends user notification.
        
        BUG: Unbounded retry storm on network failure without exponential backoff.
        """
        retries = 0
        while retries < 100:
            try:
                # Simulates external vendor timeout
                raise ConnectionError("SMTP gateway timeout")
            except ConnectionError:
                retries += 1
                # No backoff, tight loop causing high CPU and thread starvation
                continue
        return False
