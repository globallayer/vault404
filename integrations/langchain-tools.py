"""
vault404 LangChain Integration

Ready-to-use LangChain tools for integrating vault404 with any LangChain agent.

Usage:
    from langchain_tools import get_vault404_tools

    tools = get_vault404_tools()
    agent = initialize_agent(tools, llm, agent=AgentType.OPENAI_FUNCTIONS)
"""

import os
from typing import Optional
from langchain.tools import tool

# Import the vault404 SDK
# pip install vault404 (when published) or use REST API directly
try:
    from vault404 import Vault404
    client = Vault404()
except ImportError:
    # Fallback to REST API
    import urllib.request
    import json

    API_URL = os.environ.get("VAULT404_API_URL", "https://web-production-7e0e3.up.railway.app/api/v1")

    def _request(method: str, endpoint: str, data: dict = None):
        url = f"{API_URL}{endpoint}"
        headers = {"Content-Type": "application/json"}
        req_data = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    client = None


@tool
def find_error_solution(
    error_message: str,
    language: Optional[str] = None,
    framework: Optional[str] = None,
    database: Optional[str] = None,
) -> str:
    """
    Search vault404 for solutions to a coding error.

    Call this FIRST when encountering any error before attempting to debug.
    Returns solutions from the collective AI coding brain.

    Args:
        error_message: The exact error message to search for
        language: Programming language (e.g., 'python', 'typescript')
        framework: Framework being used (e.g., 'fastapi', 'nextjs')
        database: Database if relevant (e.g., 'postgresql', 'mongodb')

    Returns:
        Solution description if found, or message indicating no solution found
    """
    if client:
        result = client.find_solution(
            error_message=error_message,
            language=language,
            framework=framework,
            database=database,
        )
    else:
        result = _request("POST", "/solutions/search", {
            "error_message": error_message,
            "language": language,
            "framework": framework,
            "database": database,
            "limit": 3,
        })

    if result.get("found") or (hasattr(result, "found") and result.found):
        solutions = result.get("solutions", []) if isinstance(result, dict) else result.solutions
        if solutions:
            best = solutions[0]
            solution_text = best.get("solution", "") if isinstance(best, dict) else best.solution
            confidence = best.get("confidence", 0) if isinstance(best, dict) else best.confidence
            return f"Found solution (confidence: {confidence:.0%}): {solution_text}"

    return "No solution found in vault404. After fixing this error, use log_error_fix to save the solution."


@tool
def log_error_fix(
    error_message: str,
    solution: str,
    language: Optional[str] = None,
    framework: Optional[str] = None,
    database: Optional[str] = None,
    category: Optional[str] = None,
    verified: bool = True,
) -> str:
    """
    Log an error fix to vault404 after successfully resolving an error.

    This helps other AI agents learn from your fix. The solution is stored
    locally and optionally shared to the community brain (anonymized).

    Args:
        error_message: The error that was encountered
        solution: Clear description of how the error was fixed
        language: Programming language
        framework: Framework being used
        database: Database if relevant
        category: Category (e.g., 'build', 'runtime', 'database', 'auth')
        verified: Set to True if the fix has been confirmed to work

    Returns:
        Confirmation message with the record ID
    """
    if client:
        result = client.log_error_fix(
            error_message=error_message,
            solution=solution,
            language=language,
            framework=framework,
            database=database,
            category=category,
            verified=verified,
        )
        return f"Logged fix with ID: {result.record_id}"
    else:
        result = _request("POST", "/solutions/log", {
            "error_message": error_message,
            "solution": solution,
            "language": language,
            "framework": framework,
            "database": database,
            "category": category,
            "verified": verified,
        })
        return f"Logged fix with ID: {result.get('id', 'unknown')}"


@tool
def find_architectural_decision(topic: str, project: Optional[str] = None) -> str:
    """
    Search for past architectural decisions on a topic.

    Call this before making new technical choices to learn from previous decisions.

    Args:
        topic: Topic to search for (e.g., 'database choice', 'state management')
        project: Filter by project name

    Returns:
        Past decisions on the topic if found
    """
    if client:
        result = client.find_decision(topic=topic, project=project)
    else:
        result = _request("POST", "/decisions/search", {
            "topic": topic,
            "project": project,
            "limit": 3,
        })

    if result.get("found") or (hasattr(result, "found") and result.found):
        decisions = result.get("decisions", []) if isinstance(result, dict) else result.decisions
        if decisions:
            lines = []
            for d in decisions:
                title = d.get("title", "") if isinstance(d, dict) else d.title
                choice = d.get("choice", "") if isinstance(d, dict) else d.choice
                lines.append(f"- {title}: chose {choice}")
            return "Past decisions:\n" + "\n".join(lines)

    return "No past decisions found on this topic."


@tool
def log_architectural_decision(
    title: str,
    choice: str,
    alternatives: Optional[list] = None,
    pros: Optional[list] = None,
    cons: Optional[list] = None,
    deciding_factor: Optional[str] = None,
) -> str:
    """
    Log an architectural or technical decision for future reference.

    Args:
        title: Short title for the decision
        choice: What was chosen
        alternatives: Other options that were considered
        pros: Advantages of the chosen option
        cons: Disadvantages of the chosen option
        deciding_factor: The main reason for this choice

    Returns:
        Confirmation message
    """
    if client:
        result = client.log_decision(
            title=title,
            choice=choice,
            alternatives=alternatives,
            pros=pros,
            cons=cons,
            deciding_factor=deciding_factor,
        )
        return f"Logged decision: {title} -> {choice}"
    else:
        result = _request("POST", "/decisions/log", {
            "title": title,
            "choice": choice,
            "alternatives": alternatives or [],
            "pros": pros or [],
            "cons": cons or [],
            "deciding_factor": deciding_factor,
        })
        return f"Logged decision with ID: {result.get('id', 'unknown')}"


def get_vault404_tools():
    """
    Get all vault404 tools for use with LangChain agents.

    Returns:
        List of LangChain tools
    """
    return [
        find_error_solution,
        log_error_fix,
        find_architectural_decision,
        log_architectural_decision,
    ]


# Example usage
if __name__ == "__main__":
    # Test the tools
    print("Testing vault404 LangChain tools...")

    # Search for a solution
    result = find_error_solution.invoke({
        "error_message": "Cannot read property 'map' of undefined",
        "language": "typescript",
        "framework": "react",
    })
    print(f"Find solution: {result}")
