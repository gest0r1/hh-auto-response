# HH middle Python Backend resume — current source of truth

Date: 2026-06-24

## Decision

The middle HH lane must **not** use a shortened/lean resume. The middle profile is a full copy of the current 300k `Python Backend / AI Backend` profile, with only the entry positioning and salary anchor changed for the separate HH resume.

## Resume IDs

| Lane | Resume ID | Title / positioning | Salary anchor |
|---|---|---|---:|
| Main | `b2b0d680ff1065a62b0039ed1f4f426b6d6b73` | Python Backend / AI Backend Developer | 300000 ₽ |
| Middle | `45dcf0f8ff10ab20210039ed1f70384c77345a` | Middle Python Backend Developer / AI Backend Engineer | 200000 ₽ |

## Repository profile file

```text
data/profile.aleksandr.middle_python_backend.json
```

This file is generated from `data/profile.aleksandr.json` and keeps the same full case base, skills, proof links, location, Telegram, salary flexibility notes, and background. It changes only the middle-lane headline/positioning/target roles and salary positioning.

## Non-negotiable rule

Do not rebuild the middle lane as a reduced junior/middle-only resume. The corrected direction is:

```text
Full current 300k HH resume copy
+ middle title/positioning
+ 200000 ₽ salary anchor
```

The reason: earlier lean middle drafts weakened the cover letters and hid stronger proof points. The lane exists to broaden conversion, not to erase the candidate's stronger cases.

## Case ordering preference

When a vacancy matches backend/AI/product/agent context, strong post-Viably cases should be considered before defaulting to Viably:

1. Crypto arbitrage / trading system across 30+ CEX/DEX
2. Transoff AI Sales QA
3. WhyNotAI Telegram Agents
4. HH CRM Agent
5. Viably only when it is the best concrete fit

## Operational notes

- Any HH application/form/chat action must use the CRM `applications.resume_id` for the exact vacancy/application row.
- Middle lane auto-apply wrappers must pass the middle resume ID explicitly.
- Do not infer the resume from salary, title text, or current browser-selected HH resume.
- Live HH/Avito/external sends still require explicit approval after dry-run/review.
