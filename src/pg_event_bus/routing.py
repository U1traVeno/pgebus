"""事件路由模块。"""

from __future__ import annotations
from typing import Callable, List, Tuple, Any, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from .base import DBEvent

# 定义 Endpoint 类型别名
Endpoint = Callable[[AsyncSession, DBEvent], Awaitable[Any]]


class EventRouter:
    """事件路由器。

    类似于 FastAPI 的 APIRouter，用于注册和管理事件处理函数。
    """

    def __init__(self, prefix: str = "") -> None:
        """初始化 EventRouter。

        Args:
            prefix: 路由前缀。
        """
        self.prefix = prefix
        self.event_handlers: List[Tuple[str, Endpoint]] = []

    def add_event_route(self, path: str, endpoint: Endpoint) -> None:
        """添加事件路由。

        Args:
            path: 事件路径（相对于当前 router 的 prefix）
            endpoint: 处理函数
        """
        self.event_handlers.append((path, endpoint))

    def on(self, path: str) -> Callable[[Endpoint], Endpoint]:
        """注册事件处理函数的装饰器。

        Args:
            path: 事件路径

        Returns:
            装饰器函数
        """

        def decorator(endpoint: Endpoint) -> Endpoint:
            self.add_event_route(path, endpoint)
            return endpoint

        return decorator

    def include_router(self, router: "EventRouter", prefix: str = "") -> None:
        """包含另一个路由器。

        将子路由器的所有路由添加到当前路由器中。
        路径计算规则：prefix (参数) + router.prefix (子路由) + path (路由)

        Args:
            router: 要包含的 EventRouter 实例
            prefix: 包含时的额外前缀
        """
        for path, endpoint in router.event_handlers:
            parts: List[str] = []
            if prefix:
                parts.append(prefix)
            if router.prefix:
                parts.append(router.prefix)
            if path:
                parts.append(path)

            new_path = ".".join(parts)
            self.add_event_route(new_path, endpoint)

    async def handle(self, session: AsyncSession, event: DBEvent) -> bool:
        """处理事件。

        遍历注册的路由，找到匹配的事件类型并执行处理函数。

        Args:
            session: 数据库会话
            event: 事件对象

        Returns:
            bool: 是否找到并处理了事件
        """
        event_type = event["type"]
        for path, endpoint in self.event_handlers:
            if path == event_type:
                await endpoint(session, event)
                return True
        return False
