from colorama import Fore
from langchain.agents import Tool
from langchain.schema import HumanMessage, SystemMessage

from ..utils.model_name import ChatModelName
from ..utils.models import ChatModel
from ..utils.parameters import DEFAULT_SMART_MODEL
from textwrap import dedent


class LLMFunctionTool(Tool):
    model_name: ChatModelName
    chat_llm: ChatModel
    function_definition: str
    function_description: str

    def __init__(self, name, definition, description, model_name=DEFAULT_SMART_MODEL):
        super().__init__(name=name, func=self.get_llm_response, description=description)

        self.model_name = model_name
        self.chat_llm = ChatModel(self.model_name)

    async def get_llm_response(self, args: str) -> str:
        system_message = SystemMessage(
            content=dedent(
                f"""
                これで、次のようなPython関数になりました。: ```# {self.function_description}
                {self.function_definition}```
                
                `return`の値だけを応答してください。
                """
            )
        )
        human_message = HumanMessage(content=f"{args}")

        response = await self.chat_llm.get_chat_completion(
            [system_message, human_message]
        )

        return response
