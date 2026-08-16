"""Long-lived worker process: polls Conductor for PGRN-Sortilin pipeline tasks.

Entrypoint for `nora worker start` (see spec/nora-tool-spec.md). Requires
CONDUCTOR_SERVER_URL pointed at a running Conductor server.
"""

from conductor.ai.agents import AgentRuntime

from workflows.pgrn_sortilin_agents import pipeline

if __name__ == "__main__":
    with AgentRuntime() as runtime:
        runtime.serve(pipeline)
