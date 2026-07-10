from enum import Enum

from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    RESPOND = "RESPOND"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    CREATE_PLAN = "CREATE_PLAN"
    EXECUTE = "EXECUTE"


class AgentDecision(BaseModel):
    action: DecisionType
    reasoning: str = Field(description="Why this decision was chosen")
    response_message: str | None = Field(
        default=None,
        description="Direct response to the user when action is RESPOND",
    )
    clarification_question: str | None = Field(
        default=None,
        description="Question to ask when action is ASK_CLARIFICATION",
    )
