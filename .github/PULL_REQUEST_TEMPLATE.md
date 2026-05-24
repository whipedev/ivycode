<!--
PR title must follow Conventional Commits:
  feat(scope): add X
  fix(scope): handle Y
  docs(scope): explain Z
  chore(scope): bump dep
See CONTRIBUTING.md for the full type list.
-->

## What

<!-- One paragraph: what does this PR change? -->

## Why

<!-- One paragraph: what problem does it solve, what spec section does it implement? -->

## Validation

<!-- How did you verify it works? Paste command output if relevant. -->

```
$ make check
...
```

## Checklist

- [ ] `make check` passes locally (ruff format/lint, mypy strict, pytest, ivycode doctor)
- [ ] New code has unit tests
- [ ] Public APIs have type hints and docstrings
- [ ] Spec (`PROMPT_SPEC.md`) updated if behavior changed
- [ ] README / ru_README updated if user-visible changes
- [ ] Screenshots added for UI changes
- [ ] No secrets, tokens, or private paths committed
