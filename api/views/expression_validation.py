"""
Expression Validation API for Calculated Columns

Validates SQL expressions used in calculated columns, checking:
- Column references exist
- Functions are supported
- Syntax is correct
- Types are compatible
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

# Supported functions for calculated columns
SUPPORTED_FUNCTIONS = {
    # String functions
    'CONCAT': {'type': 'string', 'min_args': 2, 'max_args': None},
    'UPPER': {'type': 'string', 'min_args': 1, 'max_args': 1},
    'LOWER': {'type': 'string', 'min_args': 1, 'max_args': 1},
    'SUBSTRING': {'type': 'string', 'min_args': 2, 'max_args': 3},
    'TRIM': {'type': 'string', 'min_args': 1, 'max_args': 1},
    'LENGTH': {'type': 'integer', 'min_args': 1, 'max_args': 1},
    'REPLACE': {'type': 'string', 'min_args': 3, 'max_args': 3},
    
    # Numeric functions
    'SUM': {'type': 'numeric', 'min_args': 1, 'max_args': 1},
    'AVG': {'type': 'numeric', 'min_args': 1, 'max_args': 1},
    'COUNT': {'type': 'integer', 'min_args': 1, 'max_args': 1},
    'MAX': {'type': 'numeric', 'min_args': 1, 'max_args': 1},
    'MIN': {'type': 'numeric', 'min_args': 1, 'max_args': 1},
    'ROUND': {'type': 'numeric', 'min_args': 1, 'max_args': 2},
    'ABS': {'type': 'numeric', 'min_args': 1, 'max_args': 1},
    'CEIL': {'type': 'numeric', 'min_args': 1, 'max_args': 1},
    'FLOOR': {'type': 'numeric', 'min_args': 1, 'max_args': 1},
    
    # Date functions
    'NOW': {'type': 'date', 'min_args': 0, 'max_args': 0},
    'CURRENT_DATE': {'type': 'date', 'min_args': 0, 'max_args': 0},
    'CURRENT_TIMESTAMP': {'type': 'date', 'min_args': 0, 'max_args': 0},
    'DATE_PART': {'type': 'numeric', 'min_args': 2, 'max_args': 2},
    'EXTRACT': {'type': 'numeric', 'min_args': 2, 'max_args': 2},
    'TO_DATE': {'type': 'date', 'min_args': 2, 'max_args': 2},
    'DATE_TRUNC': {'type': 'date', 'min_args': 2, 'max_args': 2},
    
    # Type conversion
    'CAST': {'type': 'any', 'min_args': 2, 'max_args': 2},
    'TO_CHAR': {'type': 'string', 'min_args': 1, 'max_args': 2},
    'TO_NUMBER': {'type': 'numeric', 'min_args': 1, 'max_args': 2},
    
    # Conditional
    'CASE': {'type': 'any', 'min_args': 3, 'max_args': None},
    'COALESCE': {'type': 'any', 'min_args': 2, 'max_args': None},
    'NULLIF': {'type': 'any', 'min_args': 2, 'max_args': 2},
}

# SQL operators
OPERATORS = ['+', '-', '*', '/', '=', '!=', '<>', '<', '>', '<=', '>=', 'AND', 'OR', 'NOT', 'LIKE', 'ILIKE', 'IN', 'IS', 'IS NOT']


class ExpressionValidator:
    """Validates SQL expressions for calculated columns"""
    
    def __init__(self, expression: str, available_columns: List[Dict[str, Any]], expected_data_type: Optional[str] = None):
        self.expression = expression.strip()
        self.available_columns = {col.get('name', col) if isinstance(col, dict) else col: col for col in available_columns}
        self.expected_data_type = expected_data_type
        self.errors: List[str] = []
        self.inferred_type: Optional[str] = None
        
    def validate(self) -> Dict[str, Any]:
        """Main validation method"""
        if not self.expression:
            self.errors.append("Expression cannot be empty")
            return self._build_response()
        
        # Step 1: Basic syntax check (parentheses, quotes)
        if not self._check_basic_syntax():
            return self._build_response()
        
        # Step 2: Tokenize and validate tokens
        tokens = self._tokenize()
        if not tokens:
            return self._build_response()
        
        # Step 3: Validate column references
        self._validate_columns(tokens)
        
        # Step 4: Validate functions (including CONCAT signature)
        self._validate_functions(tokens)
        
        # Step 5: Validate operator type compatibility
        self._validate_operators(tokens)
        
        # Step 6: Type inference
        self._infer_type(tokens)
        
        # Step 7: Type compatibility check
        if self.expected_data_type and self.inferred_type:
            self._check_type_compatibility()
        
        return self._build_response()
    
    def _check_basic_syntax(self) -> bool:
        """Check basic syntax: balanced parentheses, quotes"""
        # Check parentheses
        paren_count = 0
        for char in self.expression:
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
                if paren_count < 0:
                    self.errors.append("Unmatched closing parenthesis")
                    return False
        
        if paren_count != 0:
            self.errors.append("Unmatched opening parenthesis")
            return False
        
        # Check quotes (basic check)
        single_quotes = self.expression.count("'")
        if single_quotes % 2 != 0:
            self.errors.append("Unmatched single quotes")
            return False
        
        return True
    
    def _tokenize(self) -> List[str]:
        """Tokenize the expression into identifiers, operators, functions, literals"""
        # Simple tokenization - split by whitespace and operators
        # This is a simplified version; a full SQL parser would be more complex
        tokens = []
        current_token = ""
        i = 0
        
        while i < len(self.expression):
            char = self.expression[i]
            
            # Handle whitespace
            if char.isspace():
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                i += 1
                continue
            
            # Handle operators
            if char in ['+', '-', '*', '/', '=', '<', '>', '!', '(', ')', ',']:
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                
                # Check for multi-character operators
                if i + 1 < len(self.expression):
                    two_char = char + self.expression[i + 1]
                    if two_char in ['<=', '>=', '!=', '<>']:
                        tokens.append(two_char)
                        i += 2
                        continue
                
                tokens.append(char)
                i += 1
                continue
            
            # Handle quoted strings
            if char == "'":
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
                
                # Find closing quote
                end_quote = self.expression.find("'", i + 1)
                if end_quote == -1:
                    self.errors.append("Unclosed string literal")
                    return []
                
                tokens.append(self.expression[i:end_quote + 1])
                i = end_quote + 1
                continue
            
            current_token += char
            i += 1
        
        if current_token:
            tokens.append(current_token)
        
        return tokens
    
    def _validate_columns(self, tokens: List[str]) -> None:
        """Validate that all column references exist"""
        # Extract potential column names (identifiers that aren't functions, operators, or literals)
        for token in tokens:
            # Skip operators, functions, literals
            if token in OPERATORS or token.upper() in SUPPORTED_FUNCTIONS:
                continue
            
            # Skip string literals
            if token.startswith("'") and token.endswith("'"):
                continue
            
            # Skip numeric literals
            if token.replace('.', '').replace('-', '').isdigit():
                continue
            
            # Skip parentheses and commas
            if token in ['(', ')', ',']:
                continue
            
            # This might be a column reference
            # Check if it exists (case-insensitive)
            column_found = False
            for col_name in self.available_columns.keys():
                col_name_str = col_name if isinstance(col_name, str) else str(col_name)
                if token.upper() == col_name_str.upper() or token == col_name_str:
                    column_found = True
                    break
            
            if not column_found:
                # Check if it's a table-prefixed column (e.g., "table.column")
                if '.' in token:
                    parts = token.split('.')
                    if len(parts) == 2:
                        col_part = parts[1]
                        for col_name in self.available_columns.keys():
                            col_name_str = col_name if isinstance(col_name, str) else str(col_name)
                            if col_part.upper() == col_name_str.upper() or col_part == col_name_str:
                                column_found = True
                                break
                
                if not column_found:
                    self.errors.append(f"Unknown column: '{token}'")
    
    def _parse_function_call(self, func_name: str, start_idx: int, tokens: List[str]) -> tuple:
        """Parse a function call and return (end_index, arguments_list, has_arithmetic_in_args)"""
        if start_idx + 1 >= len(tokens) or tokens[start_idx + 1] != '(':
            return (start_idx, [], False)
        
        # Find matching closing parenthesis
        paren_count = 0
        arg_tokens = []
        i = start_idx + 2  # Skip function name and opening paren
        has_arithmetic = False
        
        while i < len(tokens):
            token = tokens[i]
            
            if token == '(':
                paren_count += 1
                arg_tokens.append(token)
            elif token == ')':
                if paren_count == 0:
                    # Found closing paren for this function
                    break
                paren_count -= 1
                arg_tokens.append(token)
            elif token == ',' and paren_count == 0:
                # Argument separator at top level
                arg_tokens.append(token)
            else:
                arg_tokens.append(token)
                # Check for arithmetic operators
                if token in ['+', '-', '*', '/']:
                    has_arithmetic = True
            
            i += 1
        
        # Parse arguments (split by commas at top level)
        arguments = []
        current_arg = []
        paren_level = 0
        
        for token in arg_tokens:
            if token == '(':
                paren_level += 1
                current_arg.append(token)
            elif token == ')':
                paren_level -= 1
                current_arg.append(token)
            elif token == ',' and paren_level == 0:
                if current_arg:
                    arguments.append(' '.join(current_arg))
                    current_arg = []
            else:
                current_arg.append(token)
        
        if current_arg:
            arguments.append(' '.join(current_arg))
        
        return (i, arguments, has_arithmetic)
    
    def _validate_functions(self, tokens: List[str]) -> None:
        """Validate that all function names are supported and have correct signatures"""
        i = 0
        while i < len(tokens):
            token = tokens[i]
            token_upper = token.upper()
            
            if token_upper in SUPPORTED_FUNCTIONS:
                func_info = SUPPORTED_FUNCTIONS[token_upper]
                
                # Parse function call
                end_idx, arguments, has_arithmetic = self._parse_function_call(token, i, tokens)
                
                if end_idx == i:
                    # Function not followed by opening parenthesis
                    self.errors.append(f"Function '{token}' must be followed by opening parenthesis")
                    i += 1
                    continue
                
                # Validate CONCAT specifically
                if token_upper == 'CONCAT':
                    if len(arguments) < 2:
                        self.errors.append(
                            f"CONCAT expects at least 2 comma-separated arguments (CONCAT(a, b, ...)). "
                            f"Found {len(arguments)} argument(s)."
                        )
                    
                    # Check if CONCAT has arithmetic operators inside (incorrect usage)
                    if has_arithmetic:
                        # Check if it's a single argument with arithmetic (like CONCAT(a + b))
                        if len(arguments) == 1:
                            self.errors.append(
                                "CONCAT expects comma-separated arguments (CONCAT(a, b, ...)). "
                                "Use commas instead of '+' for concatenation."
                            )
                        else:
                            # Multiple arguments but one has arithmetic - warn but allow if it's numeric
                            pass
                
                # Validate argument count for other functions
                min_args = func_info.get('min_args', 0)
                max_args = func_info.get('max_args')
                
                if len(arguments) < min_args:
                    self.errors.append(
                        f"Function '{token}' requires at least {min_args} argument(s), "
                        f"but found {len(arguments)}"
                    )
                
                if max_args is not None and len(arguments) > max_args:
                    self.errors.append(
                        f"Function '{token}' accepts at most {max_args} argument(s), "
                        f"but found {len(arguments)}"
                    )
                
                i = end_idx + 1
            else:
                i += 1
    
    def _get_column_type(self, column_name: str) -> Optional[str]:
        """Get the datatype of a column"""
        # Handle table-prefixed columns
        if '.' in column_name:
            column_name = column_name.split('.')[-1]
        
        for col_name, col_info in self.available_columns.items():
            col_name_str = col_name if isinstance(col_name, str) else str(col_name)
            if column_name.upper() == col_name_str.upper() or column_name == col_name_str:
                if isinstance(col_info, dict):
                    return col_info.get('datatype', 'TEXT')
                return 'TEXT'
        return None
    
    def _normalize_type(self, datatype: str) -> str:
        """Normalize datatype to base type"""
        datatype_upper = datatype.upper()
        if datatype_upper in ['STRING', 'TEXT', 'VARCHAR', 'CHAR']:
            return 'STRING'
        elif datatype_upper in ['INTEGER', 'INT', 'BIGINT', 'SMALLINT']:
            return 'INTEGER'
        elif datatype_upper in ['DECIMAL', 'NUMERIC', 'FLOAT', 'DOUBLE', 'REAL']:
            return 'DECIMAL'
        elif datatype_upper in ['BOOLEAN', 'BOOL']:
            return 'BOOLEAN'
        elif datatype_upper in ['DATE', 'TIMESTAMP', 'DATETIME', 'TIME']:
            return 'DATE'
        return 'STRING'  # Default
    
    def _validate_operators(self, tokens: List[str]) -> None:
        """Validate operator type compatibility"""
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            # Check for '+' operator (most problematic for type mismatches)
            if token == '+':
                # Find left and right operands
                left_operand = None
                right_operand = None
                
                # Look backwards for left operand
                j = i - 1
                while j >= 0:
                    if tokens[j] not in ['(', ')', ','] and tokens[j] not in OPERATORS:
                        left_operand = tokens[j]
                        break
                    j -= 1
                
                # Look forwards for right operand
                j = i + 1
                while j < len(tokens):
                    if tokens[j] not in ['(', ')', ','] and tokens[j] not in OPERATORS:
                        right_operand = tokens[j]
                        break
                    j += 1
                
                # Get types of operands
                if left_operand and right_operand:
                    left_type = None
                    right_type = None
                    
                    # Check if operands are columns
                    if not (left_operand.startswith("'") and left_operand.endswith("'")):
                        if not left_operand.replace('.', '').replace('-', '').isdigit():
                            left_type = self._get_column_type(left_operand)
                    
                    if not (right_operand.startswith("'") and right_operand.endswith("'")):
                        if not right_operand.replace('.', '').replace('-', '').isdigit():
                            right_type = self._get_column_type(right_operand)
                    
                    # Normalize types
                    if left_type:
                        left_type = self._normalize_type(left_type)
                    if right_type:
                        right_type = self._normalize_type(right_type)
                    
                    # Validate type compatibility for '+'
                    if left_type and right_type:
                        # '+' is only valid for:
                        # - Numeric + Numeric
                        # - Date + Interval (simplified: allow Date + anything numeric)
                        # - String + String (but should use CONCAT instead)
                        
                        incompatible_pairs = [
                            ('BOOLEAN', 'STRING'),
                            ('STRING', 'BOOLEAN'),
                            ('BOOLEAN', 'INTEGER'),
                            ('INTEGER', 'BOOLEAN'),
                            ('BOOLEAN', 'DECIMAL'),
                            ('DECIMAL', 'BOOLEAN'),
                        ]
                        
                        if (left_type, right_type) in incompatible_pairs:
                            self.errors.append(
                                f"Operator '+' is not supported between types {left_type} and {right_type}. "
                                f"Use CONCAT() for string concatenation or ensure both operands are numeric."
                            )
                        elif left_type == 'STRING' and right_type == 'STRING':
                            # Suggest CONCAT instead
                            self.errors.append(
                                "Use CONCAT() for string concatenation instead of '+'. "
                                f"Example: CONCAT({left_operand}, {right_operand})"
                            )
            
            i += 1
    
    def _infer_type(self, tokens: List[str]) -> None:
        """Infer the data type of the expression"""
        # Check for string functions
        has_string_func = any(token.upper() in ['CONCAT', 'UPPER', 'LOWER', 'SUBSTRING', 'TRIM', 'REPLACE', 'TO_CHAR'] 
                             for token in tokens)
        if has_string_func:
            self.inferred_type = 'STRING'
            return
        
        # Check for numeric functions
        has_numeric_func = any(token.upper() in ['SUM', 'AVG', 'COUNT', 'MAX', 'MIN', 'ROUND', 'ABS', 'CEIL', 'FLOOR', 'TO_NUMBER']
                              for token in tokens)
        if has_numeric_func:
            self.inferred_type = 'INTEGER' if 'COUNT' in [t.upper() for t in tokens] else 'DECIMAL'
            return
        
        # Check for date functions
        has_date_func = any(token.upper() in ['NOW', 'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'TO_DATE', 'DATE_TRUNC', 'DATE_PART', 'EXTRACT']
                           for token in tokens)
        if has_date_func:
            self.inferred_type = 'DATE'
            return
        
        # Check for arithmetic operators (suggests numeric, but validate types first)
        has_arithmetic = any(op in tokens for op in ['+', '-', '*', '/'])
        if has_arithmetic:
            # Type inference for arithmetic depends on operand types
            # For now, default to DECIMAL (will be validated by operator validation)
            self.inferred_type = 'DECIMAL'
            return
        
        # Default to STRING if we can't determine
        self.inferred_type = 'STRING'
    
    def _check_type_compatibility(self) -> None:
        """Check if inferred type matches expected type"""
        if not self.inferred_type or not self.expected_data_type:
            return
        
        # Type mapping for compatibility
        type_map = {
            'STRING': ['STRING', 'TEXT', 'VARCHAR'],
            'INTEGER': ['INTEGER', 'INT', 'BIGINT'],
            'DECIMAL': ['DECIMAL', 'NUMERIC', 'FLOAT', 'DOUBLE', 'REAL'],
            'DATE': ['DATE', 'TIMESTAMP', 'DATETIME'],
            'BOOLEAN': ['BOOLEAN', 'BOOL'],
        }
        
        expected_upper = self.expected_data_type.upper()
        inferred_upper = self.inferred_type.upper()
        
        # Check if types are compatible
        compatible = False
        for base_type, variants in type_map.items():
            if inferred_upper == base_type or inferred_upper in variants:
                if expected_upper == base_type or expected_upper in variants:
                    compatible = True
                    break
        
        if not compatible:
            self.errors.append(
                f"Type mismatch: Expression returns {self.inferred_type}, but {self.expected_data_type} was selected"
            )
    
    def _build_response(self) -> Dict[str, Any]:
        """Build the validation response"""
        return {
            "success": len(self.errors) == 0,
            "errors": self.errors,
            "inferred_type": self.inferred_type,
        }


class ValidateExpressionView(APIView):
    """API endpoint for validating calculated column expressions"""
    
    authentication_classes = [JWTCookieAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Validate a calculated column expression
        
        Request body:
        {
            "expression": "CONCAT(firstname, ' ', lastname)",
            "expected_data_type": "STRING",
            "available_columns": [
                {"name": "firstname", "datatype": "TEXT"},
                {"name": "lastname", "datatype": "TEXT"}
            ],
            "allowed_functions": ["CONCAT", "UPPER", "LOWER", ...]  # Optional
        }
        
        Response:
        {
            "success": true/false,
            "errors": ["error1", "error2"],
            "inferred_type": "STRING"
        }
        """
        try:
            expression = request.data.get('expression', '').strip()
            expected_data_type = request.data.get('expected_data_type')
            available_columns = request.data.get('available_columns', [])
            allowed_functions = request.data.get('allowed_functions')  # Optional override
            
            if not expression:
                return Response(
                    {"success": False, "errors": ["Expression is required"], "inferred_type": None},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not available_columns:
                return Response(
                    {"success": False, "errors": ["Available columns are required"], "inferred_type": None},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Normalize available_columns format
            normalized_columns = []
            for col in available_columns:
                if isinstance(col, dict):
                    normalized_columns.append(col)
                elif isinstance(col, str):
                    normalized_columns.append({"name": col, "datatype": "TEXT"})
                else:
                    normalized_columns.append({"name": str(col), "datatype": "TEXT"})
            
            # Create validator
            validator = ExpressionValidator(
                expression=expression,
                available_columns=normalized_columns,
                expected_data_type=expected_data_type
            )
            
            # Override allowed functions if provided
            if allowed_functions:
                global SUPPORTED_FUNCTIONS
                original_functions = SUPPORTED_FUNCTIONS.copy()
                SUPPORTED_FUNCTIONS = {k: v for k, v in SUPPORTED_FUNCTIONS.items() if k in allowed_functions}
            
            # Validate
            result = validator.validate()
            
            # Restore original functions if overridden
            if allowed_functions:
                SUPPORTED_FUNCTIONS = original_functions
            
            logger.info(f"Expression validation: {result['success']}, errors: {result['errors']}")
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error validating expression: {e}", exc_info=True)
            return Response(
                {"success": False, "errors": [f"Validation error: {str(e)}"], "inferred_type": None},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

