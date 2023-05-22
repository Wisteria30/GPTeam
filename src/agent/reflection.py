from pydantic import BaseModel, Field


class ReflectionQuestions(BaseModel):
    questions: tuple[str, str, str] = Field(description="私たちが答えられる質問")


class ReflectionInsight(BaseModel):
    insight: str = Field(description="The insight")
    related_statements: list[int] = Field(
        description="洞察を裏付ける発言番号のリスト"
    )


class ReflectionResponse(BaseModel):
    insights: list[ReflectionInsight] = Field(
        description="洞察とそれを裏付ける発言番号の一覧です。"
    )
