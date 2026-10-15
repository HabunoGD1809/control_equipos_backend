import asyncio
import logging
from contextlib import suppress
from sqlalchemy.engine import make_url
from psycopg import Connection
from threading import Event
from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationBroker:
    """Bounded fan-out; PostgreSQL broadcasts committed events across processes."""
    def __init__(self):
        self.queues = {}
        self.loop = None
        self.task = None
        self.stop_event = Event()

    def subscribe(self, user_id):
        self.loop = asyncio.get_running_loop()
        queue = asyncio.Queue(maxsize=1)
        self.queues.setdefault(user_id, set()).add(queue)
        return queue

    def unsubscribe(self, user_id, queue):
        queues = self.queues.get(user_id)
        if queues:
            queues.discard(queue)
            if not queues:
                self.queues.pop(user_id, None)

    async def publish(self, user_id, count=None):
        for queue in tuple(self.queues.get(user_id, ())):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(count)

    def notify(self, user_id):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.publish(str(user_id)), self.loop)

    async def start(self):
        self.loop = asyncio.get_running_loop()
        self.stop_event.clear()
        self.task = asyncio.create_task(asyncio.to_thread(self._listen))

    async def stop(self):
        self.stop_event.set()
        if self.task:
            await self.task
        self.queues.clear()

    def _listen(self):
        url = make_url(str(settings.DATABASE_URI))
        while not self.stop_event.is_set():
            try:
                with Connection.connect(host=url.host, port=url.port, user=url.username,
                    password=url.password, dbname=url.database, autocommit=True, connect_timeout=5) as connection:
                    connection.execute("LISTEN control_equipos_notificaciones")
                    logger.info("Notificaciones en tiempo real conectadas a PostgreSQL.")
                    while not self.stop_event.is_set():
                        for notification in connection.notifies(timeout=1, stop_after=50):
                            self.notify(notification.payload)
            except Exception:
                logger.warning("Canal de notificaciones desconectado; reconexión en 5 segundos.")
                self.stop_event.wait(5)

broker = NotificationBroker()
