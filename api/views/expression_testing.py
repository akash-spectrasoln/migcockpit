"""
Expression Testing API for Calculated Columns

Executes test cases against calculated column expressions to validate runtime behavior.
"""

import re
import logging
from typing import Dict, List, Any, Optional
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from api.authentications import JWTCookieAuthentication
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


class ExpressionTestEngine:
    """Executes test cases against SQL expressions"""
    
    def __init__(self, expression: str, available_columns: List[Dict[str, Any]]):
        self.expression = expression
        self.available_columns = {col['name']: col.get('datatype', 'TEXT') for col in available_columns}
    
    def apply_null_safety(self, expr: str) -> str:
        """Apply NULL safety rules to string functions"""
        # Wrap string function arguments with COALESCE
        # UPPER(col) -> UPPER(COALESCE(col, ''))
        # LOWER(col) -> LOWER(COALESCE(col, ''))
        # CONCAT(a, b) -> CONCAT(COALESCE(a, ''), COALESCE(b, ''))
        
        empty_str = "''"
        
        # Handle CONCAT
        def replace_concat(match):
            args = match.group(1).split(',')
            coalesced_args = [f'COALESCE({arg.strip()}, {empty_str})' for arg in args]
            return f"CONCAT({', '.join(coalesced_args)})"
        
        expr = re.sub(
            r'CONCAT\s*\(([^)]+)\)',
            replace_concat,
            expr,
            flags=re.IGNORECASE
        )
        
        # Handle UPPER
        def replace_upper(match):
            return f"UPPER(COALESCE({match.group(1).strip()}, {empty_str}))"
        
        expr = re.sub(
            r'UPPER\s*\(([^)]+)\)',
            replace_upper,
            expr,
            flags=re.IGNORECASE
        )
        
        # Handle LOWER
        def replace_lower(match):
            return f"LOWER(COALESCE({match.group(1).strip()}, {empty_str}))"
        
        expr = re.sub(
            r'LOWER\s*\(([^)]+)\)',
            replace_lower,
            expr,
            flags=re.IGNORECASE
        )
        
        # Handle SUBSTRING
        def replace_substring(match):
            arg1 = match.group(1).strip()
            arg2 = match.group(2).strip()
            arg3 = match.group(3).strip() if match.group(3) else None
            if arg3:
                return f"SUBSTRING(COALESCE({arg1}, {empty_str}), {arg2}, {arg3})"
            else:
                return f"SUBSTRING(COALESCE({arg1}, {empty_str}), {arg2})"
        
        expr = re.sub(
            r'SUBSTRING\s*\(([^,]+),\s*([^,]+)(?:,\s*([^)]+))?\)',
            replace_substring,
            expr,
            flags=re.IGNORECASE
        )
        
        return expr
    
    def evaluate_test(self, test_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate expression with test input row
        
        Returns:
        {
            "success": bool,
            "result": any,
            "error": str or None,
            "sql": str  # Generated SQL for debugging
        }
        """
        try:
            # IMPORTANT: Replace column references FIRST, then apply NULL safety
            # This ensures column names are replaced before they get wrapped in COALESCE
            sql_expression = self.expression
            
            # Replace column references with test values
            # Test input values always take precedence - replace all column names in test_input
            for col_name, col_value in test_input.items():
                # Replace column name with value (test values take precedence)
                if col_value is None:
                    sql_value = "NULL"
                elif isinstance(col_value, str):
                    # Escape single quotes by doubling them
                    escaped_value = col_value.replace("'", "''")
                    sql_value = f"'{escaped_value}'"
                elif isinstance(col_value, (int, float)):
                    sql_value = str(col_value)
                elif isinstance(col_value, bool):
                    sql_value = "TRUE" if col_value else "FALSE"
                else:
                    escaped_str = str(col_value).replace("'", "''")
                    sql_value = f"'{escaped_str}'"
                
                # Replace column references
                # Handle multiple formats: regular names, bracketed [name], and quoted "name"
                escaped_col_name = re.escape(col_name)
                
                # Replace bracketed column names: [column name]
                sql_expression = re.sub(
                    rf'\[{escaped_col_name}\]',
                    sql_value,
                    sql_expression,
                    flags=re.IGNORECASE
                )
                
                # Replace quoted column names: "column name" or 'column name'
                sql_expression = re.sub(
                    rf'["\']{escaped_col_name}["\']',
                    sql_value,
                    sql_expression,
                    flags=re.IGNORECASE
                )
                
                # Replace regular column names (word boundaries to avoid partial matches)
                # Use case-insensitive replacement to handle case variations
                sql_expression = re.sub(
                    rf'\b{escaped_col_name}\b',
                    sql_value,
                    sql_expression,
                    flags=re.IGNORECASE
                )
            
            # Now apply NULL safety (wraps string function arguments with COALESCE)
            safe_expression = self.apply_null_safety(sql_expression)
            sql_expression = safe_expression
            
            # Evaluate with nested function support and intermediate logging
            result, evaluation_steps = self._simulate_evaluation_with_steps(sql_expression, test_input)
            
            return {
                "success": True,
                "result": result,
                "error": None,
                "sql": sql_expression,
                "debug_steps": evaluation_steps
            }
            
        except Exception as e:
            logger.error(f"Error evaluating test: {str(e)}", exc_info=True)
            return {
                "success": False,
                "result": None,
                "error": str(e),
                "sql": None
            }
    
    def _simulate_evaluation_with_steps(self, sql_expr: str, test_input: Dict[str, Any]) -> tuple:
        """
        Simulate SQL expression evaluation with intermediate step logging for nested functions.
        Returns (result, debug_steps) where debug_steps contains each function evaluation.
        """
        debug_steps = []
        result = self._simulate_evaluation_recursive(sql_expr, test_input, debug_steps, depth=0)
        return result, debug_steps
    
    def _simulate_evaluation_recursive(self, sql_expr: str, test_input: Dict[str, Any], debug_steps: list, depth: int) -> Any:
        """
        Recursively evaluate nested functions, logging each step.
        """
        import re
        
        def extract_nested_parens(expr: str, start_pos: int) -> tuple:
            """Extract content between parentheses, handling nesting"""
            if start_pos >= len(expr) or expr[start_pos] != '(':
                return None, start_pos
            start_pos += 1
            content = ''
            depth = 1
            pos = start_pos
            while pos < len(expr) and depth > 0:
                if expr[pos] == '(':
                    depth += 1
                elif expr[pos] == ')':
                    depth -= 1
                    if depth == 0:
                        return content, pos + 1
                content += expr[pos]
                pos += 1
            return content, pos
        
        def extract_value_from_coalesce(expr: str) -> str:
            """Extract the actual value from COALESCE(arg, '') or just return the value"""
            coalesce_pattern = r"COALESCE\s*\(([^,]+),\s*''\)"
            match = re.search(coalesce_pattern, expr, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return expr.strip()
        
        def get_string_value(value_str: str) -> str:
            """Extract string value, handling quotes and NULL"""
            value_str = value_str.strip()
            if (value_str.startswith("'") and value_str.endswith("'")) or \
               (value_str.startswith('"') and value_str.endswith('"')):
                value_str = value_str[1:-1]
            value_str = value_str.replace("''", "'")
            if value_str == 'NULL':
                return ''
            return value_str
        
        # Check for nested functions - process innermost first
        # Look for function calls that contain other function calls
        
        # Handle SUBSTRING(UPPER(...), ...) - nested case
        substring_upper_match = re.search(r'SUBSTRING\s*\(\s*UPPER\s*\(', sql_expr, re.IGNORECASE)
        if substring_upper_match:
            # Extract the full SUBSTRING call
            start_pos = substring_upper_match.start()
            args_expr, end_pos = extract_nested_parens(sql_expr, start_pos + len('SUBSTRING'))
            if args_expr:
                # Split arguments
                parts = []
                current_part = ''
                paren_depth = 0
                for char in args_expr:
                    if char == '(':
                        paren_depth += 1
                        current_part += char
                    elif char == ')':
                        paren_depth -= 1
                        current_part += char
                    elif char == ',' and paren_depth == 0:
                        parts.append(current_part.strip())
                        current_part = ''
                    else:
                        current_part += char
                if current_part:
                    parts.append(current_part.strip())
                
                if parts and parts[0].upper().startswith('UPPER'):
                    # Evaluate UPPER first
                    upper_arg_expr, _ = extract_nested_parens(parts[0], parts[0].index('('))
                    upper_arg = extract_value_from_coalesce(upper_arg_expr)
                    upper_input = get_string_value(upper_arg)
                    upper_output = upper_input.upper()
                    
                    debug_steps.append({
                        'stage': 'UPPER',
                        'input': upper_input,
                        'output': upper_output,
                        'depth': depth + 1
                    })
                    
                    # Now evaluate SUBSTRING with UPPER result
                    start = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
                    length = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
                    if length:
                        substring_output = upper_output[start-1:start-1+length] if start > 0 and start <= len(upper_output) else ''
                    else:
                        substring_output = upper_output[start-1:] if start > 0 and start <= len(upper_output) else ''
                    
                    debug_steps.append({
                        'stage': 'SUBSTRING',
                        'input': upper_output,
                        'output': substring_output,
                        'args': parts[1:],
                        'depth': depth
                    })
                    
                    return substring_output
        
        # Handle UPPER(COALESCE(...))
        upper_match = re.search(r'UPPER\s*\(', sql_expr, re.IGNORECASE)
        if upper_match:
            start_pos = upper_match.end()
            arg_expr, _ = extract_nested_parens(sql_expr, start_pos - 1)
            if arg_expr:
                arg = extract_value_from_coalesce(arg_expr)
                arg = get_string_value(arg)
                result = arg.upper()
                debug_steps.append({
                    'stage': 'UPPER',
                    'input': arg,
                    'output': result,
                    'depth': depth
                })
                return result
        
        # Handle LOWER(COALESCE(...))
        lower_match = re.search(r'LOWER\s*\(', sql_expr, re.IGNORECASE)
        if lower_match:
            start_pos = lower_match.end()
            arg_expr, _ = extract_nested_parens(sql_expr, start_pos - 1)
            if arg_expr:
                arg = extract_value_from_coalesce(arg_expr)
                arg = get_string_value(arg)
                result = arg.lower()
                debug_steps.append({
                    'stage': 'LOWER',
                    'input': arg,
                    'output': result,
                    'depth': depth
                })
                return result
        
        # Handle CONCAT(COALESCE(...), COALESCE(...))
        concat_pattern = r'CONCAT\s*\((.*?)\)'
        concat_match = re.search(concat_pattern, sql_expr, re.IGNORECASE | re.DOTALL)
        if concat_match:
            args_str = concat_match.group(1)
            # Split by comma, handling nested parentheses
            args = []
            current_arg = ''
            paren_depth = 0
            for char in args_str:
                if char == '(':
                    paren_depth += 1
                    current_arg += char
                elif char == ')':
                    paren_depth -= 1
                    current_arg += char
                elif char == ',' and paren_depth == 0:
                    args.append(current_arg.strip())
                    current_arg = ''
                else:
                    current_arg += char
            if current_arg:
                args.append(current_arg.strip())
            
            # Extract values from each COALESCE
            values = []
            for arg in args:
                value = extract_value_from_coalesce(arg)
                value = get_string_value(value)
                values.append(value)
            
            result = ''.join(values)
            debug_steps.append({
                'stage': 'CONCAT',
                'input': values,
                'output': result,
                'depth': depth
            })
            return result
        
        # Handle SUBSTRING(COALESCE(...), start, length)
        substring_pattern = r'SUBSTRING\s*\(([^,]+),\s*(\d+)(?:,\s*(\d+))?\)'
        substring_match = re.search(substring_pattern, sql_expr, re.IGNORECASE)
        if substring_match:
            arg_expr = substring_match.group(1).strip()
            start = int(substring_match.group(2))
            length = int(substring_match.group(3)) if substring_match.group(3) else None
            arg = extract_value_from_coalesce(arg_expr)
            arg = get_string_value(arg)
            if not arg:
                result = ''
            else:
                # SQL SUBSTRING is 1-indexed
                if length:
                    result = arg[start-1:start-1+length] if start > 0 and start <= len(arg) else ''
                else:
                    result = arg[start-1:] if start > 0 and start <= len(arg) else ''
            
            debug_steps.append({
                'stage': 'SUBSTRING',
                'input': arg,
                'output': result,
                'args': [str(start)] + ([str(length)] if length else []),
                'depth': depth
            })
            return result
        
        # Default: return the expression as-is (for simple column references)
        result = sql_expr.strip()
        if result.startswith("'") and result.endswith("'"):
            return result[1:-1].replace("''", "'")
        return result
    
    def _simulate_evaluation(self, sql_expr: str, test_input: Dict[str, Any]) -> Any:
        """Legacy method - use _simulate_evaluation_with_steps for nested function support"""
        result, _ = self._simulate_evaluation_with_steps(sql_expr, test_input)
        return result
        """Simulate SQL expression evaluation (for testing without database)"""
        # This is a simplified simulation - in production, execute against test DB
        
        def extract_value_from_coalesce(expr: str) -> str:
            """Extract the actual value from COALESCE(arg, '') or just return the value"""
            # Match COALESCE(arg, '')
            coalesce_pattern = r"COALESCE\s*\(([^,]+),\s*''\)"
            match = re.search(coalesce_pattern, expr, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return expr.strip()
        
        def get_string_value(value_str: str) -> str:
            """Extract string value, handling quotes and NULL"""
            value_str = value_str.strip()
            # Remove surrounding quotes
            if (value_str.startswith("'") and value_str.endswith("'")) or \
               (value_str.startswith('"') and value_str.endswith('"')):
                value_str = value_str[1:-1]
            # Unescape doubled quotes
            value_str = value_str.replace("''", "'")
            if value_str == 'NULL':
                return ''
            return value_str
        
        def extract_nested_parens(expr: str, start_pos: int) -> tuple:
            """Extract content between parentheses, handling nesting"""
            if start_pos >= len(expr) or expr[start_pos] != '(':
                return None, start_pos
            start_pos += 1
            content = ''
            depth = 1
            pos = start_pos
            while pos < len(expr) and depth > 0:
                if expr[pos] == '(':
                    depth += 1
                elif expr[pos] == ')':
                    depth -= 1
                    if depth == 0:
                        return content, pos + 1
                content += expr[pos]
                pos += 1
            return content, pos
        
        # Handle UPPER(COALESCE(...))
        upper_match = re.search(r'UPPER\s*\(', sql_expr, re.IGNORECASE)
        if upper_match:
            start_pos = upper_match.end()
            arg_expr, _ = extract_nested_parens(sql_expr, start_pos - 1)
            if arg_expr:
                arg = extract_value_from_coalesce(arg_expr)
                arg = get_string_value(arg)
                result = arg.upper()
                logger.debug(f"[Test Eval] UPPER: input='{arg}' -> output='{result}'")
                return result
        
        # Handle LOWER(COALESCE(...))
        lower_match = re.search(r'LOWER\s*\(', sql_expr, re.IGNORECASE)
        if lower_match:
            start_pos = lower_match.end()
            arg_expr, _ = extract_nested_parens(sql_expr, start_pos - 1)
            if arg_expr:
                arg = extract_value_from_coalesce(arg_expr)
                arg = get_string_value(arg)
                return arg.lower()
        
        # Handle CONCAT(COALESCE(...), COALESCE(...))
        concat_pattern = r'CONCAT\s*\((.*?)\)'
        concat_match = re.search(concat_pattern, sql_expr, re.IGNORECASE | re.DOTALL)
        if concat_match:
            args_str = concat_match.group(1)
            # Split by comma, handling nested parentheses
            args = []
            current_arg = ''
            paren_depth = 0
            for char in args_str:
                if char == '(':
                    paren_depth += 1
                    current_arg += char
                elif char == ')':
                    paren_depth -= 1
                    current_arg += char
                elif char == ',' and paren_depth == 0:
                    args.append(current_arg.strip())
                    current_arg = ''
                else:
                    current_arg += char
            if current_arg:
                args.append(current_arg.strip())
            
            # Extract values from each COALESCE
            values = []
            for arg in args:
                value = extract_value_from_coalesce(arg)
                value = get_string_value(value)
                values.append(value)
            return ''.join(values)
        
        # Handle SUBSTRING(COALESCE(...), start, length)
        # Need to handle COALESCE wrapping - extract the full first argument including nested functions
        substring_match = re.search(r'SUBSTRING\s*\(', sql_expr, re.IGNORECASE)
        if substring_match:
            start_pos = substring_match.end()
            args_expr, end_pos = extract_nested_parens(sql_expr, start_pos - 1)
            if args_expr:
                # Split arguments (handling nested parentheses and COALESCE)
                parts = []
                current_part = ''
                paren_depth = 0
                for char in args_expr:
                    if char == '(':
                        paren_depth += 1
                        current_part += char
                    elif char == ')':
                        paren_depth -= 1
                        current_part += char
                    elif char == ',' and paren_depth == 0:
                        parts.append(current_part.strip())
                        current_part = ''
                    else:
                        current_part += char
                if current_part.strip():
                    parts.append(current_part.strip())
                
                if parts:
                    # First argument may be wrapped in COALESCE
                    first_arg = parts[0]
                    arg = extract_value_from_coalesce(first_arg)
                    arg = get_string_value(arg)
                    
                    # Get start position (second argument)
                    start = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 1
                    # Get length (third argument, optional)
                    length = int(parts[2]) if len(parts) > 2 and parts[2].strip().isdigit() else None
                    
                    if not arg:
                        result = ''
                    else:
                        # SQL SUBSTRING is 1-indexed
                        if length:
                            result = arg[start-1:start-1+length] if start > 0 and start <= len(arg) else ''
                        else:
                            result = arg[start-1:] if start > 0 and start <= len(arg) else ''
                    
                    debug_steps.append({
                        'stage': 'SUBSTRING',
                        'input': arg,
                        'output': result,
                        'args': [str(start)] + ([str(length)] if length else []),
                        'depth': depth
                    })
                    return result
        
        # Default: return the expression as-is (for simple column references)
        result = sql_expr.strip()
        if result.startswith("'") and result.endswith("'"):
            return result[1:-1].replace("''", "'")
        return result


class TestExpressionView(APIView):
    """API endpoint for testing calculated column expressions with test cases"""
    
    authentication_classes = [JWTCookieAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Test a calculated column expression with test cases
        
        Request body:
        {
            "expression": "UPPER(firstname)",
            "available_columns": [
                {"name": "firstname", "datatype": "TEXT"}
            ],
            "test_cases": [
                {
                    "input": {"firstname": "abc"},
                    "expected": "ABC",
                    "description": "UPPER converts to uppercase"
                }
            ]
        }
        
        Response:
        {
            "success": true,
            "results": [
                {
                    "test": {...},
                    "passed": true/false,
                    "actual": "ABC",
                    "error": null
                }
            ]
        }
        """
        try:
            expression = request.data.get('expression', '').strip()
            available_columns = request.data.get('available_columns', [])
            test_cases = request.data.get('test_cases', [])
            
            if not expression:
                return Response(
                    {"success": False, "error": "Expression is required", "results": []},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not test_cases:
                return Response(
                    {"success": False, "error": "At least one test case is required", "results": []},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create test engine
            engine = ExpressionTestEngine(expression, available_columns)
            
            # Execute all test cases
            results = []
            for test_case in test_cases:
                test_input = test_case.get('input', {})
                expected = test_case.get('expected')
                description = test_case.get('description', 'Test case')
                
                # Evaluate
                eval_result = engine.evaluate_test(test_input)
                
                if eval_result['success']:
                    actual = eval_result['result']
                    # Normalize for comparison
                    actual_str = '' if actual is None else str(actual)
                    expected_str = '' if expected is None else str(expected)
                    
                    passed = actual_str == expected_str
                    results.append({
                        "test": {
                            "input": test_input,
                            "expected": expected,
                            "description": description
                        },
                        "passed": passed,
                        "actual": actual,
                        "error": None,
                        "sql": eval_result.get('sql'),
                        "debug_steps": eval_result.get('debug_steps', [])  # Include intermediate evaluation steps
                    })
                else:
                    results.append({
                        "test": {
                            "input": test_input,
                            "expected": expected,
                            "description": description
                        },
                        "passed": False,
                        "actual": None,
                        "error": eval_result.get('error', 'Evaluation failed'),
                        "sql": eval_result.get('sql')
                    })
            
            return Response({
                "success": True,
                "results": results
            })
            
        except Exception as e:
            logger.error(f"Error in TestExpressionView: {str(e)}", exc_info=True)
            return Response(
                {"success": False, "error": str(e), "results": []},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

