import math
import re

def calculate(expression: str) -> str:
    """
    Safely evaluates a mathematical expression containing numbers, 
    basic operators, and standard math functions (like sqrt, sin, cos, pi).
    """
    expression = expression.strip()
    
    # Define allowed functions and constants
    allowed_names = {
        'sqrt': math.sqrt,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'log': math.log,
        'log10': math.log10,
        'exp': math.exp,
        'pi': math.pi,
        'e': math.e,
        'pow': pow,
        'abs': abs
    }
    
    # 1. Verify that any alphabetic words are explicitly whitelisted
    words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', expression)
    for word in words:
        if word not in allowed_names:
            return f"Error: Unsafe or unsupported function or variable '{word}' in expression."
            
    # 2. Prevent invalid special characters
    if not re.match(r'^[a-zA-Z0-9_.\s+\-*/()%,]+$', expression):
        return "Error: Invalid characters in mathematical expression."
        
    try:
        # Evaluate in a restricted global environment with no access to builtins
        result = eval(expression, {"__builtins__": None}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"