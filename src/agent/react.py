from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .plans import LLMSinglePlan


class Reaction(Enum):
    CONTINUE = "継続"
    POSTPONE = "延期"
    CANCEL = "中止"


class LLMReactionResponse(BaseModel):
    reaction: Reaction = Field(
        description="メッセージに対する反応。「継続」、「延期」、「中止」のいずれかでなければならない。それ以外を指定してはいけない。"
    )
    thought_process: str = Field(
        description="最近起こったこと、その反応が選ばれた理由、該当する場合は現在のプランの代わりに何をすべきかを要約したものです。このような形式で言い表す: '私のプランを継続/延期/中止すべきなのは、...'です。"
    )
    new_plan: Optional[LLMSinglePlan] = Field(
        None, description="反応が「延期」である場合、このフィールドは、新しいプランを指定するために含まれるべきである。"
    )
