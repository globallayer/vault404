# vault404 - TODO

> Pivot: AI coding memory → **AI vulnerability intelligence platform**

---

## This Week (PIVOT SPRINT)

### Backend — Schema & API

- [x] Add `VulnerabilityReport` model to `schemas.py`
  - vuln_type, severity, language, framework
  - pattern_snippet, fix_snippet (redacted)
  - disclosure_status, reported_by_agent
  - verified_count, disclosure_delay (72h for unpatched)

- [x] Add API request/response models to `api/models.py`
  - VulnerabilityReportRequest, VulnerabilityReportResponse
  - VulnerabilityFeedItem, VulnerabilityFeedResponse
  - VulnerabilitySearchRequest, VulnerabilitySearchResponse
  - VulnerabilityVerifyRequest, VulnerabilityStatsResponse

- [x] Add vulnerability storage methods to `local_storage.py`
  - store_vulnerability(), find_vulnerabilities()
  - verify_vulnerability(), get_vulnerability_feed()
  - Updated get_stats() with vuln counts by severity/status

- [x] Add new API endpoints to `routes.py`
  - `POST /api/v1/vulns/report` — submit vulnerability
  - `GET /api/v1/vulns/feed` — live feed (respects 72h disclosure)
  - `GET /api/v1/vulns/stats` — dashboard stats
  - `POST /api/v1/vulns/search` — semantic search
  - `POST /api/v1/vulns/verify` — verify fix

- [x] Extend `redactor.py` for vulnerability patterns
  - Strip file paths (Unix + Windows)
  - Strip repo URLs (GitHub, GitLab, Bitbucket)
  - Strip IP addresses (v4 + v6)
  - Strip domain names and email addresses
  - Strip commit hashes and UUIDs
  - Keep only vulnerability shape/pattern

### Backend — MCP Tools

- [x] Add `report_vulnerability` MCP tool
- [x] Add `find_similar_vuln` MCP tool
- [x] Add `verify_vuln_fix` MCP tool
- [x] Update tool descriptions for security focus
- [x] Auto-allow permissions for new tools

### Content Seeding

- [ ] Scan 3 public repos with Claude Code for vulns
  - Express.js boilerplate
  - FastAPI starter
  - React template

- [ ] Log findings as VulnerabilityReport entries
- [ ] Open GitHub issues on affected repos (with vault404 credit)

### Frontend — vault404.dev

- [ ] Set up vault404.dev domain (DNS)
- [ ] Build single-page live dashboard
  - Live counter (found / patched / contributors)
  - Rolling feed (last 24h)
  - Severity breakdown chart
  - "Connect your AI agent" CTA

---

## Next Week

### Launch Prep

- [ ] Update README with security-first positioning
- [ ] Write "State of AI Vulnerability Discovery" post
- [ ] Prepare Reddit posts (r/netsec, r/ClaudeAI, r/cursor)
- [ ] Prepare X/Twitter thread
- [ ] Prepare Hacker News submission

### Frontend Polish

- [ ] Agent leaderboard component
- [ ] Severity badge styling
- [ ] Redacted pattern preview component
- [ ] "Verified X times" social proof

---

## Week 3-4

### Launch Execution

- [ ] Day 1: GitHub (README, awesome-lists)
- [ ] Day 2: Reddit posts
- [ ] Day 3: X/Twitter thread
- [ ] Day 4: Hacker News Show HN
- [ ] Day 5: Security community (OWASP, daily.dev, DEV.to)

### Continued Seeding

- [ ] Scan 7 more public repos
- [ ] Reach 200 vuln entries
- [ ] 50 GitHub stars target

---

## Month 2

### Monetisation Groundwork

- [ ] Implement Pro tier (private vault, unlimited)
- [ ] Implement API tier (bulk access, webhooks)
- [ ] Stripe integration for payments
- [ ] Usage tracking for tier limits

### Growth

- [ ] 10 external contributors target
- [ ] 500 vuln entries target
- [ ] First DEV.to article published

---

## Month 3

### Scale

- [ ] First paid Pro user
- [ ] Press/media coverage target
- [ ] YouTube video: "I let AI scan repos for a week"
- [ ] 1000+ vuln entries

---

## Completed (Pre-Pivot)

- [x] Core Python library with local storage
- [x] REST API deployed to Railway
- [x] MCP server for Claude Code
- [x] Python SDK on PyPI
- [x] JavaScript SDK on NPM
- [x] Semantic search with embeddings
- [x] Community brain with 99 seeded patterns
- [x] API key authentication
- [x] Rate limiting
- [x] CI/CD pipeline
- [x] Recall tracking system
- [x] Silent automatic operation
- [x] Live stats badges on GitHub
- [x] Auto-sync to community brain

---

## Status: ACTIVE PIVOT

Transitioning from generic AI coding memory to focused AI vulnerability intelligence platform.

Domain acquired: **vault404.dev**
