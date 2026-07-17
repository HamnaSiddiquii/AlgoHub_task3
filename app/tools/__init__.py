from .calculator import calculator_tool
from .file_reader import file_reader_tool, list_files_tool
from .code_executor import code_executor_tool
from .web_search import web_search_tool

ALL_TOOLS = [
    calculator_tool,
    file_reader_tool,
    list_files_tool,
    code_executor_tool,
    web_search_tool,
]
