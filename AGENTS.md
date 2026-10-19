# Development rules

- Follow plan -> code -> test -> review, with focused iteration branches.
- Public configuration uses CLI arguments. JSON is evidence or internal data.
- CPU evidence tooling must import without torch or accelerator runtimes.
- Preserve PASS / FAIL / INCONCLUSIVE. Missing evidence is not PASS.
- Preserve exact upstream revisions, model identity and verification scope.
- Run `python -m unittest discover -s tests -v` for CPU tests; record remote
  accelerator commands, actual exits and any checks not run.
- All commits must use `git commit -s`.
- Each iteration must use a pull request. Record the problem, mechanism,
  alternatives, validation evidence, rejected results and remaining limitations.
- The repository owner authorized creating this private repository and merging
  iteration PRs on 2026-10-19. Review and green checks precede merging. Research
  results may merge with an explicit failed/inconclusive performance outcome;
  never describe such a merge as meeting the overall performance objective.
- Do not publish packages or activate production systems.
