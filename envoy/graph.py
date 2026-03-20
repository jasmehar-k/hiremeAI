"""LangGraph orchestration for the application pipeline."""

import asyncio
from typing import TypedDict

from langgraph.graph import StateGraph, END

from envoy import config
from envoy.nodes.filter import GraphState, filter_node
from envoy.nodes.generation import (
    resume_writer_node,
    cover_letter_writer_node,
    qa_answerer_node,
)
from envoy.nodes.renderer import renderer_node
from envoy.nodes.applicator import applicator_node
from envoy.nodes import discovery
from envoy import tracker


def create_graph() -> StateGraph:
    """Create the LangGraph state machine."""

    # Define the graph
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("filter", filter_node)
    workflow.add_node("resume_writer", resume_writer_node)
    workflow.add_node("cover_letter_writer", cover_letter_writer_node)
    workflow.add_node("qa_answerer", qa_answerer_node)
    workflow.add_node("renderer", renderer_node)
    workflow.add_node("applicator", applicator_node)

    # Set entry point
    workflow.set_entry_point("filter")

    # Conditional edge after filter
    workflow.add_conditional_edges(
        "filter",
        route_after_filter,
        {
            "generation": "resume_writer",
            "end": END,
        }
    )

    # Generation runs in parallel (after filter)
    # Note: For true parallelism in LangGraph, we'd use Send API
    # For simplicity, we run sequentially but they operate independently
    workflow.add_edge("resume_writer", "cover_letter_writer")
    workflow.add_edge("cover_letter_writer", "qa_answerer")
    workflow.add_edge("qa_answerer", "renderer")
    workflow.add_edge("renderer", "applicator")
    workflow.add_edge("applicator", END)

    return workflow.compile()


def route_after_filter(state: GraphState) -> str:
    """Route to generation or end based on fit score."""
    if state.get("status") == "skipped":
        return "end"
    return "generation"


async def run_for_job(job: dict) -> GraphState:
    """Run the pipeline for a single job."""
    # Initial state
    initial_state: GraphState = {
        "job": job,
        "profile_context": "",
        "fit_score": 0.0,
        "resume_data": {},
        "cover_letter": "",
        "qa_answers": {},
        "pdf_path": "",
        "status": "pending",
    }

    # Log initial application
    tracker.log_application(
        job_id=job.get("id", ""),
        company=job.get("company", ""),
        title=job.get("title", ""),
        url=job.get("url", ""),
        platform=job.get("platform", ""),
        portal_type=job.get("portal_type"),
        status="pending",
    )

    # Run the graph
    graph = create_graph()
    result = await graph.ainvoke(initial_state)

    return result


async def run_cycle() -> list[GraphState]:
    """
    Run one complete cycle of the application pipeline.

    Discovers jobs, filters by fit score, generates application materials,
    and submits where applicable.
    """
    # Discover jobs
    print("Discovering job listings...")
    jobs = await discovery.discover_all()
    print(f"Found {len(jobs)} new job listings")

    if not jobs:
        print("No new jobs to process")
        return []

    # Run pipeline for each job (with concurrency limit)
    results = []
    semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_APPLICATIONS)

    async def run_with_limit(job):
        async with semaphore:
            try:
                return await run_for_job(job)
            except Exception as e:
                print(f"Error processing job {job.get('title')} at {job.get('company')}: {e}")
                return None

    results = await asyncio.gather(*[run_with_limit(job) for job in jobs])
    results = [r for r in results if r is not None]

    # Summary
    submitted = sum(1 for r in results if r.get("status") == "submitted")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    failed = sum(1 for r in results if r.get("status") == "failed")
    manual = sum(1 for r in results if r.get("status") == "manual_review")

    print(f"\nCycle complete:")
    print(f"  Submitted: {submitted}")
    print(f"  Skipped (low fit): {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Manual review: {manual}")

    return results


def main():
    """CLI entry point to run one cycle."""
    results = asyncio.run(run_cycle())
    return results


if __name__ == "__main__":
    main()