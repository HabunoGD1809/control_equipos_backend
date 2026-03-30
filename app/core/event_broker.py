import asyncio
from typing import Dict, Set

class NotificationBroker:
    """
    Broker de eventos en memoria para manejar conexiones SSE.
    Permite el patrón Pub/Sub sin necesidad de Redis.
    """
    def __init__(self):
        self.queues: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, user_id: str) -> asyncio.Queue:
        """Crea una nueva cola para un cliente conectado."""
        if user_id not in self.queues:
            self.queues[user_id] = set()
        queue = asyncio.Queue()
        self.queues[user_id].add(queue)
        return queue

    def unsubscribe(self, user_id: str, queue: asyncio.Queue):
        """Elimina la cola cuando el cliente se desconecta."""
        if user_id in self.queues:
            self.queues[user_id].discard(queue)
            if not self.queues[user_id]:
                del self.queues[user_id]

    async def publish(self, user_id: str, count: int):
        """Envía el nuevo conteo a todas las pestañas/dispositivos conectados del usuario."""
        if user_id in self.queues:
            for queue in self.queues[user_id]:
                await queue.put(count)

broker = NotificationBroker()
