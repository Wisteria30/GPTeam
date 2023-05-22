from pydantic import BaseModel, Field

from src.tools.context import ToolContext
from src.utils.database.base import Tables
from src.utils.database.client import get_database
from src.utils.embeddings import get_embedding

# pydantic model for the document tool


class SaveDocumentToolInput(BaseModel):
    """Input for the document tool."""

    title: str = Field(..., description="ファイルの名前")
    document: str = Field(..., description="ファイルの内容")


async def save_document(title: str, document: str, tool_context: ToolContext):
    normalized_title = title.lower().strip().replace(" ", "_")

    await (await get_database()).insert_document_with_embedding(
        {
            "title": title,
            "normalized_title": normalized_title,
            "content": document,
            "agent_id": str(tool_context.agent_id),
        },
        f"""{title} ({normalized_title})
{document}""",
    )

    return f"Document saved: {title}"


class ReadDocumentToolInput(BaseModel):
    """Input for the document tool."""

    title: str = Field(..., description="ファイルの名前")


async def read_document(title: str, tool_context: ToolContext):
    normalized_title = title.lower().strip().replace(" ", "_")
    try:
        document = (
            await (await get_database()).get_by_field(
                Tables.Documents, "normalized_title", normalized_title
            )
        )[0]["content"]
    except Exception:
        return f"Document not found: {title}"
    return f"""Document found: {title}
Content:
{document}"""


class SearchDocumentsToolInput(BaseModel):
    """Input for the document tool."""

    query: str = Field(..., description="ドキュメントクエリ")


async def search_documents(query: str, tool_context: ToolContext):
    # documents = await (await get_database()).search_document_embeddings(query, 10)
    if True:
        return f"クエリに該当するドキュメントは見つかりませんでした。: {query}"
    document_names = (
        '"' + '"\n"'.join(map(lambda document: document["title"], documents)) + '"'
    )
    return f"""Documents found for query "{query}": 
{document_names}"""
