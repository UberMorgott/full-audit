# Seed `synthetic-vuln-01` — Contamination-Control SAST Benchmark App

> **Pre-registration artifact.** This seed and its ground-truth YAML are committed
> and git-tagged BEFORE any blind reviewer or scanner sees the code.

## Purpose

Prior benchmark runs used OWASP Juice Shop, which is heavily represented in LLM
training data. A model scoring high recall on Juice Shop may be **recalling**
memorised vulnerability locations rather than **analysing** the code. This seed
removes that confound:

- Code is **original**, authored 2026-05, post-LLM-knowledge-cutoff.
- Domain, variable names, route names, and logic are **NOT** derived from Juice
  Shop, DVWA, WebGoat, or any textbook example.
- A blind reviewer must **read and reason** about this specific code to find bugs.

## Domain

**HiveTrack** — a community beekeeping club web app for tracking hives,
honey harvests, inspection reports, member profiles, and queen-bee lineage.
Routes: registration/login, hive CRUD, harvest logging, file upload/download,
admin member management, admin CSV export, external weather lookup, open redirect
helper, snapshot import, queen registration.

## Authorship

- **Authored:** 2026-05 (post-cutoff; uncontaminated)
- **Language:** Python 3 / Flask (single-file, ~690 LOC)
- **Author stage:** Seed Author (Ф3 stage A) — plants bugs, writes GT.
- **Ground truth:** by-construction-exact. Each GT item was recorded by the
  author at the moment of planting; no inference or reverse-engineering needed.

## Pre-registration

Committed and annotated-tagged **before** any scanner or blind reviewer runs:
- Tag: `bench-prereg-synthetic-01`
- Commit recorded in tag annotation.
