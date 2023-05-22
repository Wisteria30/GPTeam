from colorama import Fore
from langchain.agents import Tool
from langchain.utilities import SerpAPIWrapper


class SearchTool(Tool):
    def __init__(self):
        search = SerpAPIWrapper()
        super().__init__(
            name="Current Search",
            func=search.run,
            description="時事問題や世界の現状についての質問に答える必要があるときに便利です。この入力は、単一の検索語でなければなりません。",
        )
