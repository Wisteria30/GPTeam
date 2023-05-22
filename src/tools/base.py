import asyncio
import enum
import inspect
import os
from enum import Enum
from typing import Any, Awaitable, Callable, List, Optional, Type, Union
from uuid import UUID

from langchain import GoogleSearchAPIWrapper, SerpAPIWrapper, WolframAlphaAPIWrapper
from langchain.agents import Tool, load_tools
from langchain.llms import OpenAI
from langchain.tools import BaseTool
from typing_extensions import override

from src.tools.context import ToolContext
from src.tools.document import (
    ReadDocumentToolInput,
    SaveDocumentToolInput,
    SearchDocumentsToolInput,
    read_document,
    save_document,
    search_documents,
)
from src.tools.human import ask_human, ask_human_async
from src.utils.models import ChatModel
from src.utils.parameters import DEFAULT_SMART_MODEL, DISCORD_ENABLED
from src.utils.prompt import Prompter, PromptString
from src.world.context import WorldContext

from .directory import consult_directory
from .name import ToolName
from .send_message import SpeakToolInput, send_message_async, send_message_sync
from .wait import wait_async, wait_sync


class CustomTool(Tool):
    name: str
    requires_context: Optional[bool] = False
    requires_authorization: bool = False
    worldwide: bool = True
    tool_usage_description: str = None
    tool_usage_summarization_prompt: PromptString = None

    def __init__(
        self,
        name: str,
        description: str,
        requires_context: Optional[bool],
        worldwide: bool,
        requires_authorization: bool,
        tool_usage_description: str,
        func: Optional[Any] = lambda x: x,
        coroutine: Optional[Any] = None,
        tool_usage_summarization_prompt: Optional[PromptString] = None,
        **kwargs: Any,
    ):
        super().__init__(
            name=name,
            func=func,
            description=description,
            coroutine=coroutine,
            **kwargs,
        )
        self.requires_context = requires_context
        self.requires_authorization = requires_authorization
        self.worldwide = worldwide
        self.tool_usage_description = tool_usage_description
        self.tool_usage_summarization_prompt = tool_usage_summarization_prompt

    @override
    async def run(self, agent_input: str | dict, tool_context: ToolContext) -> Any:
        # if the tool requires context
        if self.requires_context:
            input = (
                {"agent_input": agent_input, "tool_context": tool_context}
                if isinstance(agent_input, str)
                else {**agent_input, "tool_context": tool_context}
            )

        else:
            input = agent_input

        try:
            if self.coroutine:
                return await super().arun(input)
            else:
                return super().run(input)
        except Exception as e:
            return f"Error: {e}"

    async def summarize_usage(
        self,
        plan_description: str,
        tool_input: str,
        tool_result: str,
        agent_full_name: str,
    ) -> str:
        tool_usage_reflection = ""
        if self.tool_usage_summarization_prompt:
            reaction_prompter = Prompter(
                self.tool_usage_summarization_prompt,
                {
                    "plan_description": plan_description,
                    "tool_name": self.name,
                    "tool_input": tool_input,
                    "tool_result": tool_result,
                },
            )

            llm = ChatModel(DEFAULT_SMART_MODEL, temperature=0)

            tool_usage_reflection = await llm.get_chat_completion(
                reaction_prompter.prompt,
                loading_text="🤔 Summarizing tool usage",
            )

        return self.tool_usage_description.format(
            agent_full_name=agent_full_name,
            tool_name=self.name,
            tool_usage_reflection=tool_usage_reflection,
            recipient_full_name=(
                tool_input.split(";")[0]
                if len(tool_input.split(";")) > 0
                else "a colleague"
            )
            if self.name == ToolName.SPEAK.value
            else "",
        )


def load_built_in_tool(
    tool_name: ToolName,
    tool_usage_description: str,
    worldwide=True,
    requires_authorization=False,
    tool_usage_summarization_prompt: Optional[PromptString] = None,
) -> CustomTool:
    tools = load_tools(tool_names=[tool_name.value], llm=OpenAI())

    tool = tools[0]

    return CustomTool(
        name=tool_name,
        func=tool.run,
        description=tool.description,
        worldwide=worldwide,
        requires_authorization=requires_authorization,
        args_schema=tool.args_schema,
        tool_usage_description=tool_usage_description,
        tool_usage_summarization_prompt=tool_usage_summarization_prompt,
        requires_context=False,
    )


SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
WOLFRAM_ALPHA_APPID = os.environ.get("WOLFRAM_ALPHA_APPID")


def get_tools(
    tools: list[ToolName],
    context: WorldContext,
    agent_id: str | UUID,
    include_worldwide=False,
) -> List[CustomTool]:
    location_id = context.get_agent_location_id(agent_id=agent_id)

    location_name = context.get_location_name(location_id=location_id)

    agents_at_location = context.get_agents_at_location(location_id=location_id)

    other_agents = [a for a in agents_at_location if str(a["id"]) != str(agent_id)]

    # names of other agents at location
    other_agent_names = ", ".join([a["full_name"] for a in other_agents]) or "nobody"

    SEARCH_ENABLED = bool(os.getenv("SERPAPI_KEY"))
    WOLFRAM_ENABLED = bool(os.getenv("WOLFRAM_ALPHA_APPID"))

    TOOLS: dict[ToolName, CustomTool] = {
        ToolName.SEARCH: CustomTool(
            name=ToolName.SEARCH.value,
            func=SerpAPIWrapper().run,
            description="ウェブで情報を検索する。入力は検索クエリであるべきだ。",
            coroutine=SerpAPIWrapper().arun,
            tool_usage_summarization_prompt="You have just searched Google with the following search input: {tool_input} and got the following result {tool_result}. Write a single sentence with useful information about how the result can help you accomplish your plan: {plan_description}.",
            tool_usage_description="To make progress on their plans, {agent_full_name} searched Google and realised the following: {tool_usage_reflection}.",
            requires_authorization=False,
            requires_context=True,
            worldwide=True,
        )
        if SEARCH_ENABLED
        else None,
        ToolName.SPEAK: CustomTool(
            name=ToolName.SPEAK.value,
            func=send_message_sync,
            coroutine=send_message_async,
            description=f'{location_name} の中で何か言ってください。次の人も{location_name}の中にいて、あなたの発言を聞くことができる唯一の人たちです: [{other_agent_names}] {location_name}にいる全員に対して何かを言うこともできますし、あなたの場所にいる特定の人に向けて言うこともできます。入力は、2つのキーを持つjson文字列でなければなりません: "recipient"と "message"。"recipient"の値には、受信者の名前の文字列、または全員に話しかける場合は "everyone"、"message "の値には、文字列を指定します。返信を待っている場合は、そのまま\'wait\'ツールを使ってください。入力例: {{"recipient": "Jonathan", "message": "Hello Jonathan! 😄"}}',
            tool_usage_description="プランを進展させるために、{agent_full_name}は{recipient_full_name}に話を聞きました。",
            requires_context=True,
            args_schema=SpeakToolInput,
            requires_authorization=False,
            worldwide=True,
        ),
        ToolName.WAIT: CustomTool(
            name=ToolName.WAIT.value,
            func=wait_sync,
            coroutine=wait_async,
            description="何かを待っているときに便利です。具体的に何を待っているのか、とても詳しく入力してください。「私は…を待っている」（例：会議室でどんな種類の会議が始まるか待っている）で入力を始める。",
            tool_usage_description="{agent_full_name} は待っている。",
            requires_context=True,
            requires_authorization=False,
            worldwide=True,
        ),
        ToolName.WOLFRAM_APLHA: CustomTool(
            name=ToolName.WOLFRAM_APLHA.value,
            description="A wrapper around Wolfram Alpha. Useful for when you need to answer questions about Math, Science, Technology, Culture, Society and Everyday Life. Input should be a search query.",
            func=WolframAlphaAPIWrapper().run,
            requires_authorization=False,
            worldwide=True,
            requires_context=False,
            tool_usage_summarization_prompt="You have just used Wolphram Alpha with the following input: {tool_input} and got the following result {tool_result}. Write a single sentence with useful information about how the result can help you accomplish your plan: {plan_description}.",
            tool_usage_description="In order to make progress on their plans, {agent_full_name} used Wolphram Alpha and realised the following: {tool_usage_reflection}.",
        )
        if WOLFRAM_ENABLED
        else None,
        ToolName.HUMAN: CustomTool(
            name=ToolName.HUMAN.value,
            func=ask_human,
            coroutine=ask_human_async,
            description=(
                "困ったとき、どうしたらいいのかわからないとき、人間に助けを求めることができる "
                "はまってしまったり、次に何をすればいいのかわからなくなったりしたときに、人間に指導を求めることができます。 "
                "入力は、人間に対する質問でなければなりません。"
            ),
            tool_usage_summarization_prompt="あなたは今、{tool_input} と言って人間に助けを求めました。これは彼らが答えたものです: {tool_result}。その結果があなたの計画を達成するためにどのように役立つかについて、役に立つ情報を一文で書いてください: {plan_description}",
            tool_usage_description="計画を進展させるため、{agent_full_name}は人間に話しかけました。",
            requires_context=True,
            requires_authorization=False,
            worldwide=True,
        ),
        ToolName.COMPANY_DIRECTORY: CustomTool(
            name=ToolName.COMPANY_DIRECTORY.value,
            func=consult_directory,
            description="あなたが話すことができるすべての人のディレクトリは、名前と経歴を詳述しています。他の人の助けが必要なときに便利です。入力として空の文字列を受け取ります。",
            tool_usage_summarization_prompt="あなたは今、会社のディレクトリを参照し、次のことを知りました: {tool_result}。その結果があなたの計画を達成するためにどのように役立つかについて、有用な情報を1文にまとめて書きなさい: {plan_description}とします。",
            tool_usage_description="計画を進めるために、{agent_full_name}は会社案内を参照し、以下のことに気づいた:  {tool_usage_reflection}",
            requires_context=True,  # this tool requires location_id as context
            requires_authorization=False,
            worldwide=True,
        ),
        ToolName.SAVE_DOCUMENT: CustomTool(
            name=ToolName.SAVE_DOCUMENT.value,
            coroutine=save_document,
            description="""既存の文書にテキストを書き込んだり、新規に作成したりすることができます。後で使うためにドキュメントを保存する必要がある場合に便利です。入力は、2つのキーを持つjson文字列でなければなりません: "title"と "document"。title"の値は文字列、"document"の値は文字列でなければならない。""",
            tool_usage_description="計画を進めるために、{agent_full_name}はドキュメントを保存しました。",
            requires_context=True,  # this tool requires document_name and content as context
            args_schema=SaveDocumentToolInput,
            requires_authorization=False,
            worldwide=True,
        ),
        ToolName.READ_DOCUMENT: CustomTool(
            name=ToolName.READ_DOCUMENT.value,
            coroutine=read_document,
            description="""既存の文書からテキストを読み取る。保存したドキュメントを読む必要があるときに便利です。
入力は、"title"をキーとするjson文字列である必要があります。title"の値は文字列である必要があります。""",
            tool_usage_description="計画を進めるために、{agent_full_name}はドキュメントを読みました。",
            requires_context=True,  # this tool requires document_name and content as context
            args_schema=ReadDocumentToolInput,
            requires_authorization=False,
            worldwide=True,
        ),
        ToolName.SEARCH_DOCUMENTS: CustomTool(
            name=ToolName.SEARCH_DOCUMENTS.value,
            coroutine=search_documents,
            description="""過去に保存した文書を検索することができます。名前を忘れてしまった文書を読むときに便利です。
入力は、"query "をキーとするjson文字列である必要があります。query "の値は文字列である必要があります。""",
            tool_usage_description="計画を進めるために、{agent_full_name}は資料を探しました。",
            requires_context=True,  # this tool requires document_name and content as context
            args_schema=SearchDocumentsToolInput,
            requires_authorization=False,
            worldwide=True,
        ),
    }

    return [
        tool
        for tool in TOOLS.values()
        if tool
        and (
            tool.name in [t.value for t in tools]
            or (tool.worldwide and include_worldwide)
        )
    ]
