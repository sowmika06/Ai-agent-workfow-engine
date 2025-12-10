from typing import Dict, Any, Callable
import re


class ToolRegistry:
    """Registry for workflow tools/functions"""
    
    def __init__(self):
        """Initialize tool registry with default code review tools."""
        self.tools: Dict[str, Callable] = {}
        self._register_default_tools()
    
    def register(self, name: str, func: Callable) -> None:
        """Register a new tool function in the registry."""
        self.tools[name] = func
    
    def get(self, name: str) -> Callable:
        """Retrieve a tool function by its registered name."""
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found")
        return self.tools[name]
    
    def list_tools(self) -> list:
        """Get list of all registered tool names."""
        return list(self.tools.keys())
    
    def _register_default_tools(self):
        """Register the default set of code review tools."""
        self.register("extract_functions", extract_functions)
        self.register("check_complexity", check_complexity)
        self.register("detect_issues", detect_issues)
        self.register("suggest_improvements", suggest_improvements)
        self.register("calculate_quality_score", calculate_quality_score)


# Default tool implementations

def extract_functions(state, **kwargs) -> Dict[str, Any]:
    """Extract function definitions from Python code using regex pattern matching."""
    code = state.get("code", "")
    
    if not code:
        return {"functions": [], "function_count": 0}
    
    # Regex pattern to match function definitions
    func_pattern = r'def\s+(\w+)\s*\([^)]*\):'
    functions = []
    
    for match in re.finditer(func_pattern, code):
        functions.append({
            "name": match.group(1),
            "line": code[:match.start()].count('\n') + 1
        })
    
    return {
        "functions": functions,
        "function_count": len(functions)
    }


def check_complexity(state, **kwargs) -> Dict[str, Any]:
    """Calculate cyclomatic complexity for each function in the code."""
    code = state.get("code", "")
    functions = state.get("functions", [])
    
    complexity_scores = []
    
    for func in functions:
        # Simplified cyclomatic complexity calculation
        complexity = 1  # Base complexity
        complexity += code.count('if ')
        complexity += code.count('for ')
        complexity += code.count('while ')
        
        complexity_scores.append({
            "function": func["name"],
            "complexity": complexity,
            "level": "high" if complexity > 5 else "low"
        })
    
    return {"complexity_scores": complexity_scores}


def detect_issues(state, **kwargs) -> Dict[str, Any]:
    """Detect common code quality issues like style violations and missing documentation."""
    code = state.get("code", "")
    
    if not code:
        return {"issues": [], "issue_count": 0, "severity_counts": {"high": 0, "medium": 0, "low": 0}}
    
    issues = []
    lines = code.split('\n')
    
    for i, line in enumerate(lines, 1):
        stripped_line = line.strip()
        
        # Check for long lines
        if len(line) > 100:
            issues.append({
                "type": "style", "line": i,
                "message": "Line too long (>100 characters)", "severity": "low"
            })
        
        # Check for missing docstrings
        if stripped_line.startswith('def ') and ':' in line:
            has_docstring = False
            for j in range(i, min(i + 3, len(lines))):
                if j < len(lines) and ('"""' in lines[j] or "'''" in lines[j]):
                    has_docstring = True
                    break
            
            if not has_docstring:
                issues.append({
                    "type": "documentation", "line": i,
                    "message": "Function missing docstring", "severity": "medium"
                })
        
        # Check for TODO comments
        if 'TODO' in line or 'FIXME' in line:
            issues.append({
                "type": "maintenance", "line": i,
                "message": "TODO/FIXME comment found", "severity": "low"
            })
    
    # Count issues by severity
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for issue in issues:
        severity_counts[issue["severity"]] += 1
    
    return {
        "issues": issues,
        "issue_count": len(issues),
        "severity_counts": severity_counts
    }


def suggest_improvements(state, **kwargs) -> Dict[str, Any]:
    """Generate actionable improvement suggestions based on complexity and issues analysis."""
    complexity_scores = state.get("complexity_scores", [])
    issues = state.get("issues", [])
    
    suggestions = []
    
    # Suggestions based on complexity
    for score in complexity_scores:
        if score["complexity"] > 10:
            suggestions.append({
                "type": "refactor", "target": score["function"],
                "suggestion": f"Consider breaking down {score['function']} (complexity: {score['complexity']})",
                "priority": "high"
            })
        elif score["complexity"] > 5:
            suggestions.append({
                "type": "refactor", "target": score["function"],
                "suggestion": f"Consider simplifying {score['function']} (complexity: {score['complexity']})",
                "priority": "medium"
            })
    
    # Suggestions based on issue patterns
    issue_types = {}
    for issue in issues:
        issue_types[issue["type"]] = issue_types.get(issue["type"], 0) + 1
    
    if issue_types.get("documentation", 0) > 2:
        suggestions.append({
            "type": "documentation", "target": "general",
            "suggestion": "Add docstrings to improve code documentation", "priority": "medium"
        })
    
    if issue_types.get("style", 0) > 5:
        suggestions.append({
            "type": "style", "target": "general",
            "suggestion": "Consider using a code formatter (black, autopep8)", "priority": "low"
        })
    
    return {
        "suggestions": suggestions,
        "suggestion_count": len(suggestions)
    }


def calculate_quality_score(state, **kwargs) -> Dict[str, Any]:
    """Calculate an overall code quality score based on complexity, issues, and structure."""
    function_count = state.get("function_count", 0)
    avg_complexity = state.get("average_complexity", 0)
    issue_count = state.get("issue_count", 0)
    severity_counts = state.get("severity_counts", {})
    
    # Start with perfect score and deduct for problems
    base_score = 10
    
    # Deduct for complexity
    if avg_complexity > 10:
        base_score -= 3
    elif avg_complexity > 5:
        base_score -= 1
    
    # Deduct for issues
    base_score -= severity_counts.get("high", 0) * 2
    base_score -= severity_counts.get("medium", 0) * 1
    base_score -= severity_counts.get("low", 0) * 0.5
    
    # Bonus for having functions
    if function_count > 0:
        base_score += 1
    
    # Ensure score stays within valid range
    quality_score = max(0, min(10, base_score))
    
    # Classify quality level
    if quality_score >= 8:
        quality_level = "excellent"
    elif quality_score >= 6:
        quality_level = "good"
    elif quality_score >= 4:
        quality_level = "fair"
    else:
        quality_level = "poor"
    
    return {
        "quality_score": quality_score,
        "quality_level": quality_level
    }


# Create global instance
tool_registry = ToolRegistry()