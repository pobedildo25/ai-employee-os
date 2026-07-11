from abc import ABC, abstractmethod

from app.strategy.models import StrategyRequest, StrategyResult


class StrategyStrategistInterface(ABC):
    @abstractmethod
    async def analyze(self, request: StrategyRequest, *, trace_id: str = "-") -> StrategyResult:
        raise NotImplementedError


class StrategyPlannerInterface(ABC):
    @abstractmethod
    async def plan(self, request: StrategyRequest, *, trace_id: str = "-") -> StrategyResult:
        raise NotImplementedError
