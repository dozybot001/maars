"""MCP server connections for ADK agents.

Uses community MCP servers instead of custom tool implementations.
Each function returns a McpToolset that ADK agents can use directly.
"""

from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from mcp.client.stdio import StdioServerParameters


def create_arxiv_toolset() -> McpToolset:
    """arXiv MCP server — search, download, read full papers.

    Tools provided:
    - search: Search arXiv for papers
    - download: Download a paper by ID
    - read_paper: Read a downloaded paper's full text
    - list_papers: List all downloaded papers
    """
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="python",
                args=["-m", "arxiv_mcp_server"],
            ),
        ),
    )


def create_fetch_toolset() -> McpToolset:
    """Web fetch MCP server — retrieve content from any URL.

    Tools provided:
    - fetch: Fetch a URL and return content as markdown/text
    """
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="python",
                args=["-m", "mcp_server_fetch"],
            ),
        ),
    )
