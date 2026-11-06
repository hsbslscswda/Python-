"""Capacity-one snapshots; acknowledged bounded events cannot silently disappear."""

from collections import deque
from threading import Condition, Lock

from .domain import Event


class Latest:
    def __init__(self):
        self._condition = Condition()
        self._value = None
        self._version = 0

    def publish(self, value):
        with self._condition:
            self._value = value
            self._version += 1
            self._condition.notify_all()

    def read(self, after=0, timeout=0.0):
        with self._condition:
            if self._version <= after and timeout:
                self._condition.wait_for(lambda: self._version > after, timeout)
            return self._version, self._value


class EventJournal:
    def __init__(self, capacity=128):
        self._events = deque()
        self._lock = Lock()
        self.capacity = capacity
        self.expired = 0
        self.last_id = 0

    def publish(self, event: Event):
        with self._lock:
            if event.event_id <= self.last_id:
                return
            if len(self._events) >= self.capacity:
                raise BufferError("特效事件积压：停止输入，避免静默丢失事件")
            self._events.append(event)
            self.last_id = event.event_id

    def consume(self, now: float, max_age=1.5) -> tuple[Event, ...]:
        with self._lock:
            events = tuple(self._events)
            self._events.clear()  # This atomic drain is the single consumer's acknowledgement.
            live = tuple(e for e in events if now - e.timestamp <= max_age)
            self.expired += len(events) - len(live)
            return live

    def clear(self):
        with self._lock:
            self._events.clear()
