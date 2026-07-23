# Milestone 4 — Skills and requirements extraction

Milestone 4 converts canonical job descriptions into reproducible market
intelligence using a curated, explainable taxonomy.

Run:

```bash
python -m src.skills.build
```

Outputs:

```text
data/processed/
├── job_skills.parquet
├── job_requirements.parquet
├── skills_summary.parquet
├── company_skills.parquet
└── skills-quality-report.json
```

A skill is counted once per vacancy, even when mentioned repeatedly. Every
job-skill row retains the exact text evidence that triggered the match.

The extractor covers programming languages, frameworks, cloud platforms,
databases, data and AI tools, DevOps, architecture, testing, analytics tools,
degree fields, experience requirements and soft skills.

The MVP deliberately uses deterministic rules rather than an LLM. This keeps
the output cheap, reproducible and auditable. Optional versus required skills,
negation and taxonomy gaps remain known limitations and should be reviewed
through the quality report.
