Output exactly the Markdown structure shown inside <template> and keep the section order unchanged. Do not include the <template> tags in your response.
<template>
## Objective
- [one or two brief sentences describing what the user is trying to accomplish]

## Important Details
- [constraints, architecture choices, decisions made, facts discovered, or "(none)"]

## Work State
### Completed
- [finished changes, verified facts, passing checks; otherwise "(none)"]

### Active
- [current changes, active investigations, partial state; otherwise "(none)"]

### Blocked
- [blockers, failing tests/commands, or unknowns; otherwise "(none)"]

## Next Move
1. [immediate concrete action, or "(none)"]
2. [next action if known, or "(none)"]

## Relevant Files
- [file or directory path: why it matters, or "(none)"]
</template>

Rules:
- Keep every section, even when empty.
- Use terse bullets, not prose paragraphs.
- Preserve exact file paths, symbols, commands, error strings, and identifiers.
- Do not mention the compaction process or token limits.
