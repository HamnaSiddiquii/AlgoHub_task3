import os
from typing import Optional

def read_or_list_files(file_path: Optional[str] = None) -> str:
    """
    Reads the contents of a file if a path is provided.
    If no path is provided, or the agent asks to list, it lists workspace files.
    """
    # 1. Handle directory listing requests
    if not file_path or file_path.strip().lower() in ['.', 'list', 'ls', 'workspace']:
        try:
            files = os.listdir('.')
            # Filter out virtual environments, git configs, and system files
            ignored = {'.git', '__pycache__', '.venv', 'venv', '.streamlit', '.DS_Store'}
            filtered_files = [f for f in files if f not in ignored and not f.startswith('.')]
            
            if not filtered_files:
                return "The workspace is currently empty."
            return "Files in workspace:\n" + "\n".join(f"- {f}" for f in filtered_files)
        except Exception as e:
            return f"Error listing workspace files: {str(e)}"
            
    # 2. Sanitize and resolve file path
    base_dir = os.path.abspath('.')
    target_path = os.path.abspath(file_path)
    
    # Fallback to local file lookup if path resolution attempts to escape base directory
    if not target_path.startswith(base_dir):
         target_path = os.path.join(base_dir, os.path.basename(file_path))
         
    if not os.path.exists(target_path):
        # Be helpful: if file is not found, list available workspace files
        try:
            files = os.listdir('.')
            available = [f for f in files if f not in {'.git', '__pycache__', '.venv', 'venv'}]
            return f"Error: File '{file_path}' not found. Available files: {', '.join(available)}"
        except:
            return f"Error: File '{file_path}' not found."
            
    # 3. Read directory contents if path points to a directory
    if os.path.isdir(target_path):
        try:
            files = os.listdir(target_path)
            return f"Directory '{file_path}' contains:\n" + "\n".join(f"- {f}" for f in files)
        except Exception as e:
            return f"Error reading directory: {str(e)}"
            
    # 4. Read file content
    try:
        with open(target_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"