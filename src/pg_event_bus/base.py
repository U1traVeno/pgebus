"""PostgreSQL NOTIFY/LISTEN 的基础事件系统。"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Event, EventSource


class DBEvent(Dict[str, Any]):
    """数据库事件负载结构。

    继承自 Dict 以在 Python 3.8 中支持 TypedDict 的行为。

    Attributes:
        type: 事件类型标识符 (例如 'template.version.created')
        payload: 事件特定数据
    """

    def __init__(self, type: str, payload: Dict[str, Any]) -> None:
        super().__init__(type=type, payload=payload)

    @property
    def event_type(self) -> str:
        """获取事件类型"""
        return self["type"]

    @property
    def event_payload(self) -> Dict[str, Any]:
        """获取事件负载"""
        return self["payload"]


async def publish_event(
    session: AsyncSession,
    event_type: str,
    payload: Dict[str, Any],
    source: EventSource,
    channel: str,
    run_at: Optional[datetime] = None,
) -> Event:
    """发布事件到数据库并通过 PostgreSQL NOTIFY 通知。

    Args:
        session: 数据库会话
        event_type: 事件类型标识符 (例如 'template.version.created')
        payload: 事件特定数据（应该保持薄，只包含必要的 ID）
        source: 事件来源
        channel: PostgreSQL NOTIFY 频道名称
        run_at: 延迟执行时间，None 表示立即执行

    Returns:
        创建的事件对象

    Example:
        >>> async with session.begin():
        ...     event = await publish_event(
        ...         session,
        ...         "simulation.created",
        ...         {"simulation_id": 123},
        ...         EventSource.INTERNAL,
        ...         "events",
        ...     )
    """
    # 1. 创建事件记录
    event = Event(
        type=event_type,
        payload=payload,
        source=source,
        run_at=run_at,
    )
    session.add(event)
    await session.flush()  # 获取 ID

    # 2. 发送 NOTIFY（提示有新事件）
    # NOTIFY 只是提示信号，不携带完整事件数据
    await session.execute(
        text(f"NOTIFY {channel}, :event_id"),
        {"event_id": str(event.id)},
    )

    return event
