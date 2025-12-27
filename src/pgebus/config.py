from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

JsonSerializer = Callable[[Any], str]
JsonDeserializer = Callable[[str], Any]


class EngineConfig(BaseModel):
    """SQLAlchemy Engine 配置。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    pool_size: int = 5
    max_overflow: int = 2
    pool_timeout: int = 120
    pool_pre_ping: bool = True
    pool_recycle: int = 3600

    # 透传给 create_async_engine(connect_args=...)
    connect_args: Dict[str, Any] = Field(default_factory=dict)

    # 可选 JSON 序列化器（默认使用标准库 json）
    json_serializer: Optional[JsonSerializer] = Field(default=None, repr=False)
    json_deserializer: Optional[JsonDeserializer] = Field(default=None, repr=False)

    def engine_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_pre_ping": self.pool_pre_ping,
            "pool_recycle": self.pool_recycle,
        }

        if self.connect_args:
            kwargs["connect_args"] = dict(self.connect_args)

        def _default_json_serializer(value: Any) -> str:
            return json.dumps(value, ensure_ascii=False)

        kwargs["json_serializer"] = self.json_serializer or _default_json_serializer
        kwargs["json_deserializer"] = self.json_deserializer or json.loads
        return kwargs


class DatabaseConfig(BaseModel):
    """PostgreSQL 数据库配置。"""

    host: str = "localhost"
    port: int = 5432
    database: str = "postgres"
    user: str = "postgres"
    password: str = "postgres"
    application_name: Optional[str] = None

    # 默认使用独立 schema 与业务表隔离
    model_config = ConfigDict(populate_by_name=True)
    schema_name: str = Field(default="pgebus", alias="schema")

    engine: EngineConfig = Field(default_factory=EngineConfig)

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @property
    def asyncpg_dsn(self) -> str:
        # LISTEN/NOTIFY 专用连接使用 asyncpg 原生 DSN
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @property
    def search_path(self) -> Optional[str]:
        """PostgreSQL search_path。

        默认优先在独立 schema 中解析（并保留 public 作为兜底）。
        """
        return f"{self.schema_name},public"


class EventSystemConfig(BaseModel):
    """事件系统配置（LISTEN/NOTIFY + Worker Pool）。"""

    channel: str = "events"

    n_workers: int = Field(
        default=5,
        ge=1,
        le=100,
        description="并发处理事件的 Worker 数量。根据负载和 CPU 核心数调整。",
    )
    queue_maxsize: int = Field(
        default=1000,
        ge=0,
        description="事件队列最大容量。0 表示无限制（不推荐）。队列满时会丢弃新事件。",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="事件处理失败后的最大重试次数。",
    )
    poll_interval: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Worker 在队列为空时的轮询间隔（秒）。",
    )

    shutdown_wait_timeout: float = Field(
        default=30.0,
        ge=0.0,
        description="优雅关闭时等待队列清空的超时时间（秒）。0 表示不等待。",
    )
    shutdown_wait_for_completion: bool = Field(
        default=True,
        description="优雅关闭时是否等待队列中的事件处理完毕。",
    )


class Settings(BaseSettings):
    """pgebus 配置（仅包含 DB 与事件系统）。"""

    model_config = SettingsConfigDict(
        env_prefix="PGEBUS_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    event_system: EventSystemConfig = Field(default_factory=EventSystemConfig)
