from abc import ABC, abstractmethod
from typing import Any

from app.presentation_design.models import PresentationDesignResult, PresentationPlan


class PresentationDesignerInterface(ABC):
    @abstractmethod
    async def design(
        self,
        *,
        goal: str,
        context: dict[str, Any] | None = None,
        brand_profile: dict[str, Any] | None = None,
        learning_rules: list[dict[str, Any]] | None = None,
        presentation_type: str | None = None,
        trace_id: str = "-",
    ) -> PresentationDesignResult:
        raise NotImplementedError


class PresentationPlannerInterface(ABC):
    @abstractmethod
    async def plan(
        self,
        *,
        goal: str,
        context: dict[str, Any] | None = None,
        brand_profile: dict[str, Any] | None = None,
        learning_rules: list[dict[str, Any]] | None = None,
        presentation_type: str | None = None,
        trace_id: str = "-",
    ) -> PresentationPlan:
        raise NotImplementedError
