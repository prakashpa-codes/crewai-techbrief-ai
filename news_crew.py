"""Core two-agent CrewAI workflow for TechBrief AI."""
import os
from datetime import date

from crewai import Agent, Crew, Process, Task
from crewai.tools import tool
from crewai_tools import SerperDevTool
from dotenv import load_dotenv

load_dotenv()


@tool("Get today's date")
def get_todays_date() -> str:
    """Return today's date in ISO format for time-sensitive research."""
    return date.today().isoformat()


def validate_newsletter(text: str) -> dict:
    """Check that output contains exactly five non-empty numbered lines."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    numbered = [
        line for line in lines
        if len(line) > 2 and line[0] in "12345" and line[1] in ".)"
    ]
    valid = len(lines) == 5 and len(numbered) == 5
    return {
        "valid": valid,
        "line_count": len(lines),
        "message": "Five-line format check passed." if valid
        else "Expected exactly five non-empty numbered lines.",
    }


def _check_keys():
    missing = [key for key in ("OPENAI_API_KEY", "SERPER_API_KEY")
               if not os.getenv(key, "").strip()]
    if missing:
        raise RuntimeError(
            "Missing " + ", ".join(missing) +
            ". Add these values to your local .env file."
        )


def build_crew(topic="technology", event_callback=None):
    """Build the required sequential Researcher -> Writer crew."""
    _check_keys()
    topic = topic.strip() or "technology"

    researcher = Agent(
        role="Technology News Researcher",
        goal=f"Find today's three most important credible technology stories about {topic}.",
        backstory=(
            "You are a careful technology journalist. Prefer recent, credible sources, "
            "distinguish facts from claims, and provide dates and source URLs."
        ),
        tools=[SerperDevTool(), get_todays_date],
        verbose=True,
        step_callback=event_callback,
    )
    writer = Agent(
        role="Technology Newsletter Writer",
        goal="Turn the supplied research into a concise, accurate five-line newsletter.",
        backstory=(
            "You are an experienced technology editor. Use only the research supplied "
            "in your task context. Do not perform web research or invent details."
        ),
        tools=[],
        verbose=True,
        step_callback=event_callback,
    )

    find = Task(
        description=(
            f"Research today's top three technology news stories related to '{topic}'. "
            "Use web search. For each story, provide a headline, concise factual summary, "
            "publication date when available, publisher, and source URL. Prefer stories "
            "published today; if fewer than three strong stories are available, use the "
            "most recent credible stories and state their dates. Do not invent facts or links."
        ),
        expected_output=(
            "A structured brief with exactly three distinct stories, each with headline, "
            "key facts, date if available, publisher, and source URL."
        ),
        agent=researcher,
    )
    write = Task(
        description=(
            "Use the Researcher's output passed through task context. Return exactly five "
            "non-empty numbered lines and nothing else. Lines 1-3 summarise the three stories. "
            "Line 4 begins '4. Why it matters:'. Line 5 begins '5. What to watch:'. "
            "Keep every line concise and factual. Include a source name or URL in the relevant "
            "story line when practical. No title, preamble, blank lines, or closing text."
        ),
        expected_output=(
            "Exactly five numbered lines and no other text. Lines 1-3 cover the stories; "
            "line 4 starts '4. Why it matters:'; line 5 starts '5. What to watch:'."
        ),
        agent=writer,
        context=[find],
    )
    return Crew(
        agents=[researcher, writer],
        tasks=[find, write],
        process=Process.sequential,
        verbose=True,
        task_callback=event_callback,
    )


def run_newsletter(topic="technology", event_callback=None):
    """Run the crew and return its text and deterministic format evaluation."""
    result = build_crew(topic, event_callback).kickoff()
    newsletter = str(result).strip()
    return {
        "newsletter": newsletter,
        "evaluation": validate_newsletter(newsletter),
    }


if __name__ == "__main__":
    try:
        output = run_newsletter()
        print("\n" + output["newsletter"])
        print("\nValidation:", output["evaluation"]["message"])
        if not output["evaluation"]["valid"]:
            raise SystemExit(1)
    except Exception as exc:
        print(f"Could not generate newsletter: {exc}")
        raise SystemExit(1)
