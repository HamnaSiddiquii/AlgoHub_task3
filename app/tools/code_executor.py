import sys
import os
import subprocess
import tempfile

def execute_python_code(code: str) -> str:
    """
    Executes Python code in a sandboxed subprocess and returns stdout/stderr.
    Includes a timeout guard to prevent infinite loops.
    """
    # Create a temporary file to hold the executable Python script
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w', encoding='utf-8') as temp_file:
        temp_file.write(code)
        temp_file_path = temp_file.name

    try:
        # Run the script using the active environment's Python interpreter
        result = subprocess.run(
            [sys.executable, temp_file_path],
            capture_output=True,
            text=True,
            timeout=10 # Prevents the agent from freezing your machine with infinite loops
        )
        
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\nRuntime Error:\n{result.stderr}"
            
        if not output.strip():
            output = "Code executed successfully with no printed output."
            
        return output
        
    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out (10 second limit exceeded)."
    except Exception as e:
        return f"Error executing code: {str(e)}"
    finally:
        # Cleanup file cleanup
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass