from pydantic import BaseModel, Field
class PlatformInfo(BaseModel):
    name: str
    version: str
    phase: str
class WorkflowRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=4000)
    mode: str = "research"
class LearningProgress(BaseModel):
    user_id: str
    course_id: str
    completion: float = Field(ge=0, le=1)
