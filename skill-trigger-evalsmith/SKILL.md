---
name: skill-trigger-evalsmith
description: Use when a skill's autoactivation quality matters. This skill creates realistic should-trigger and should-not-trigger eval prompts, stores them beside the skill, checks whether descriptions are too broad or too weak, and helps tune trigger metadata without keyword spam. Use for new skills, renamed skills, cross-client ports, and skills that under-trigger or over-trigger in Codex, Claude Code, or Kimi Code.
when_to_use: When creating or improving trigger behavior for a skill; when the user wants realistic activation tests; when a skill description needs tuning; when adding a skill to 0langas-skill-center and needing e2e eval prompts.
type: prompt
whenToUse: When creating or improving trigger behavior for a skill; when the user wants realistic activation tests; when a skill description needs tuning; when adding a skill to 0langas-skill-center and needing e2e eval prompts.
disableModelInvocation: false
---

# Skill Trigger Evalsmith

Use this skill to make skill activation testable. A good skill is valuable only if the agent loads it at the right time and ignores it at the right time.

## Dependency Order

Use `tri-client-skill-port` first when the skill is not yet tri-client compatible. Use `official-docs-citation-cache` when eval prompts depend on provider-specific docs or discovery behavior.

## What To Produce

For each target skill, create:

```text
<skill-name>/evals/evals.json
<skill-name>/evals/trigger-evals.json
```

`evals.json` is the simple skill-creator-style prompt list. `trigger-evals.json` is the activation-focused set.

## Trigger Eval Schema

```json
[
  {
    "id": "T001",
    "query": "realistic user prompt",
    "should_trigger": true,
    "reason": "why this skill should or should not load",
    "competing_skills": ["optional-skill-name"],
    "expected_routing": "short routing expectation"
  }
]
```

## Prompt Design Rules

- Write prompts that sound like the user, including casual phrasing, typos, paths, repo names, and real workflow context.
- Include 8-12 should-trigger cases and 8-12 should-not-trigger cases for mature skills.
- Use near-misses as negatives. Obvious unrelated negatives do not prove anything.
- Include competing-skill cases where another skill should win.
- Avoid keyword-only prompts that make the description look better than it is.
- Include at least one path-specific case, one vague-but-valid case, and one overreach case.

## Description Tuning

After generating evals, inspect the skill description:

- If should-trigger prompts need exact magic words, the description is too narrow.
- If near-miss negatives would trigger, the description is too broad.
- If another skill should own the task, make that boundary explicit in both skills.
- Prefer purpose-and-context language over long keyword lists.

## Output

```json
{
  "action": "created-trigger-evals",
  "skill": "skill-name",
  "trigger_cases": 10,
  "negative_cases": 10,
  "files": ["skill-name/evals/evals.json", "skill-name/evals/trigger-evals.json"],
  "description_recommendation": "tighten boundary with manage-memory"
}
```

