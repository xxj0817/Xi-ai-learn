"""统一响应包装。"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    code: int = 0
    message: str = "ok"
    data: DataT | None = None


def ok(data: DataT) -> ApiResponse[DataT]:
    return ApiResponse[DataT](code=0, message="ok", data=data)
