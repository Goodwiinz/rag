# Repository agent instructions

Repository context and engineering commands live in `docs/engineering/`.
Directory-specific `AGENTS.md` files add narrower rules.

## NOUS improvement loop

When the user asks for the NOUS loop, a self-improvement tick, or autonomous
iterative bug fixing, read `docs/engineering/nous-loop.md` completely before
taking action. It is the canonical cross-runtime workflow.

Runtime-specific commands are adapters only. They may map available tools onto
the canonical capability contract, but they may not weaken its evidence,
review, authorization, or terminal-outcome gates.
