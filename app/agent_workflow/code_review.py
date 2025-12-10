from app.core.models import GraphDefinition, NodeDefinition


def create_code_review_workflow() -> GraphDefinition:
    """Create the Code Review Mini-Agent workflow"""
    
    nodes = [
        NodeDefinition(
            name="extract_functions",
            function_name="extract_functions",
            parameters={}
        ),
        NodeDefinition(
            name="check_complexity",
            function_name="check_complexity",
            parameters={}
        ),
        NodeDefinition(
            name="detect_issues",
            function_name="detect_issues",
            parameters={}
        ),
        NodeDefinition(
            name="suggest_improvements",
            function_name="suggest_improvements",
            parameters={}
        ),
        NodeDefinition(
            name="calculate_quality",
            function_name="calculate_quality_score",
            parameters={}
        ),
        NodeDefinition(
            name="final_review",
            function_name="calculate_quality_score",  # Re-calculate for final check
            parameters={}
        )
    ]
    
    # Simple mapping 
    edges = {
        "extract_functions": "check_complexity",
        "check_complexity": "detect_issues", 
        "detect_issues": "suggest_improvements",
        "suggest_improvements": "calculate_quality"
        # calculate_quality and final_review have no simple edges (handled by conditional_edges)
    }
    
    # Conditional edges for branching and looping
    conditional_edges = {
        "calculate_quality": {
            "quality_score >= 7": "final_review",  # If quality good, finish
            "quality_score < 7": "suggest_improvements"  # Loop back for improvements
        }
        # final_review has no outgoing edges (workflow ends)
    }
    
    return GraphDefinition(
        name="Code Review Mini-Agent",
        nodes=nodes,
        edges=edges,
        conditional_edges=conditional_edges,
        start_node="extract_functions"
    )


# Sample code for testing
SAMPLE_CODE = '''
import os
import sys

def calculate_total(numbers):
    total = 0
    for num in numbers:
        if num > 0:
            total += num
        elif num < 0:
            total -= abs(num)
    return total

def process_data(data):
    # TODO: Add validation
    result = []
    for item in data:
        if item:
            if len(item) > 10:
                result.append(item[:10])
            else:
                result.append(item)
    return result

def complex_function(a, b, c, d, e):
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        return a + b + c + d + e
                    else:
                        return a + b + c + d - e
                else:
                    return a + b + c - d
            else:
                return a + b - c
        else:
            return a - b
    else:
        return 0
'''