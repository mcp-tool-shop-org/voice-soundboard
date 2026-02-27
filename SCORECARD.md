# Scorecard

> Score a repo before remediation. Fill this out first, then use SHIP_GATE.md to fix.

**Repo:** voice-soundboard
**Date:** 2026-02-27
**Type tags:** `[pypi]` `[cli]`

## Pre-Remediation Assessment

| Category | Score | Notes |
|----------|-------|-------|
| A. Security | 3/10 | No SECURITY.md, no threat model in README, no telemetry statement |
| B. Error Handling | 8/10 | Typed exceptions exist, CLI exit codes work |
| C. Operator Docs | 7/10 | README excellent, CHANGELOG exists but alpha-dated, LICENSE present |
| D. Shipping Hygiene | 4/10 | No verify script, no Makefile, no dep scanning, CI lint not enforced |
| E. Identity (soft) | 10/10 | Logo, translations, landing page, metadata all present |
| **Overall** | **32/50** | |

## Key Gaps

1. No SECURITY.md or threat model in README
2. No Makefile verify target or dep scanning in CI
3. No coverage reporting (pytest-cov, Codecov)
4. CI lint step not enforced (continue-on-error: true)
5. Missing Codecov badge and scorecard in README

## Remediation Priority

| Priority | Item | Estimated effort |
|----------|------|-----------------|
| 1 | Create SECURITY.md + add threat model to README | 5 min |
| 2 | Add Makefile, coverage to CI, dep-audit job | 10 min |
| 3 | Add Codecov badge, scorecard, standard footer | 5 min |

## Post-Remediation

| Category | Before | After |
|----------|--------|-------|
| A. Security | 3/10 | 10/10 |
| B. Error Handling | 8/10 | 10/10 |
| C. Operator Docs | 7/10 | 10/10 |
| D. Shipping Hygiene | 4/10 | 10/10 |
| E. Identity (soft) | 10/10 | 10/10 |
| **Overall** | 32/50 | 50/50 |
