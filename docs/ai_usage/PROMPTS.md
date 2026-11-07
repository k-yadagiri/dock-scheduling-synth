# AI Usage Disclosure

## Important notice — redaction
The complete prompt history is **not** published here. The prompts in this development session contained the text of a confidential assessment brief, recruitment correspondence and attachments. Publishing that material is restricted, so those portions have been **redacted and replaced with short non-confidential summaries**. This file is therefore a partial, honest record, not the full prompt log. If the assessor requires the complete prompt history, it is retained privately and can be provided through a channel authorized by the assessor rather than published publicly.

## AI tool used
- **Claude** (Anthropic), used through a Claude Code agent session. This is the only AI tool recorded in this session. No other AI tools are claimed here; any use outside this session is not covered by this log.

## What the AI assisted with
- Designing and writing the synthetic-data generator (`generate.py`), the schema/data dictionary source (`schema.py`) and the validator/metrics module (`validate.py`).
- Writing the automated tests, README, Makefile and data documentation.
- Generating the datasets, SQL seed files, ground-truth files, validation/metrics reports and reproducibility report by running the code.
- Packaging the project into ZIP files.
- Submission-readiness edits (`.gitignore`, closing file handles, this disclosure).

The author is responsible for reviewing, running and submitting the work.

## Prompts in this session (redacted where necessary)

### Prompt 1 — Initial build request  *(assessment text redacted)*
- **Redacted summary:** The user attached the assessment brief and related material (not reproduced here) and asked the assistant to read it and build a project covering all of its requirements: a synthetic-data project for dock/yard/labor appointment scheduling, delivered as a ZIP.
- **Non-confidential portion preserved verbatim:** "iam giving the full details about the project and iwant project in zip file  and dont use more tokens"

### Prompt 2 — Submission-readiness update
Verbatim (contains no assessment content):
```
Please make a final submission-readiness update to the existing project without rewriting or changing the working scheduling logic.

1. Add `.gitignore` for Python cache files, virtual environments and temporary files.
2. Create `docs/ai_usage/PROMPTS.md` using the actual prompts from this development session, if available. Do not invent or fabricate prompts.
3. Fix ResourceWarnings caused by unclosed file handles in `generate.py` and `validate.py`.
4. Review the README and ensure all execution commands are correct.
5. Run all nine tests, full validation and reproducibility verification again.
6. Create an updated ZIP named `dock-scheduling-synth-final.zip`.

Do not remove existing functionality or generated output data. Report actual test results and any remaining limitations.
```

### Prompt 3 — Confidentiality fix
- **Summary:** The user asked the assistant to inspect the project for confidential assessment wording and recruitment/candidate information, redact this AI usage file accordingly while keeping an honest disclosure, leave the implementation and generated data unchanged, re-run the tests, validation and reproducibility check, and produce `dock-scheduling-synth-submission.zip` without overwriting earlier ZIPs. (The prompt text itself is summarized rather than quoted.)
