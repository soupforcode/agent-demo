"""College administration triage agent — the worked example for the
"Architecting Autonomous Intelligence" workshop.

Read the modules in this order, they build on each other:

    config.py   how we talk to the model (and why it's all in one place)
    schemas.py  the contract the agent has to fill in
    tools.py    what the agent can actually *do*
    agent.py    the agent itself
    team.py     several agents with a router in front
    api.py      the whole thing as an HTTP service
"""

__version__ = "0.1.0"
