from pydantic import BaseModel, Field

from app.agents.decision.models import AgentDecision


class AgentUnderstanding(BaseModel):
    goal: str = Field(description="Main goal expressed by the user")
    summary: str = Field(description="Brief understanding of the task")
    required_capabilities: list[str] = Field(
        default_factory=list,
        description="Capabilities that may be needed to fulfill the goal",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Information needed before proceeding",
    )
    next_action: str = Field(
        description="Suggested next step, e.g. respond, request_information, create_plan, execute",
    )


class ExecutiveAgentResult(BaseModel):
    understanding: AgentUnderstanding
    decision: AgentDecision
