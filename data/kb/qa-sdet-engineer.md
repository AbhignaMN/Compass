# QA Automation & SDET Career Guide (India Freshers)

## Role Overview
Quality Assurance Automation Engineers and Software Development Engineers in Test (SDETs) build automated test suites, API contract checks, CI test gates, and performance benchmarks so engineering teams ship reliably without regressions. SDET is an excellent, high-demand entry path in Bengaluru, Pune, Hyderabad, Chennai, and Gurugram, with fresher salaries ranging from INR 35,000 to 95,000/month (internships INR 15,000 to 35,000/month).

## Core Skills & Prerequisites
Modern QA hiring favors engineers who code: Python (`pytest`) or Java/TypeScript, browser automation with Playwright or Selenium, API testing with Postman and `httpx`/Rest Assured, SQL verification queries, Git, CI/CD (GitHub Actions or Jenkins), bug lifecycle/Jira, and strong test-case design (boundary values, equivalence partitioning, negative cases). Load testing with k6 or JMeter is a major plus.

## 4-Week Learning Roadmap
- **Week 1 — Testing Fundamentals & Manual/API Verification:** Learn test pyramids, boundary-value analysis, HTTP status codes, and Postman collections with assertions. Deliverable: a structured test plan + automated Postman/Newman API collection for a public REST API.
- **Week 2 — UI Automation with Playwright or Selenium:** Build a Page Object Model (POM) test framework in Python (pytest + Playwright) or TypeScript (Playwright) covering login, search, checkout, and error states without flaky sleeps. Deliverable: GitHub repo with headless cross-browser execution and HTML reports.
- **Week 3 — Backend API, Database & Performance Testing:** Write automated API tests validating JSON schemas, auth failures, and Postgres state, plus a basic k6 or JMeter load test measuring throughput and p95 latency. Deliverable: reproducible test suite + latency summary.
- **Week 4 — CI Integration & Flake-Proofing:** Run the full API + UI suite automatically on GitHub Actions with trace/screenshot artifacts uploaded on failure.

## Free Courses & Resources
- **Test Automation University (Applitools)** (https://testautomationu.applitools.com): Free structured courses on Playwright, Selenium, API testing, and pytest.
- **Playwright Official Docs** (https://playwright.dev): Modern, reliable end-to-end testing guide.
- **Postman Academy** (https://academy.postman.com): Free API testing and automation certifications.
- **pytest Documentation** (https://docs.pytest.org): Fixtures, parametrization, and mocking patterns.
- **Grafana k6 Docs** (https://grafana.com/docs/k6/latest/): Modern developer-friendly load testing.

## Portfolio Projects & Interview Prep
Showcase a clean automation framework testing a real web app (like an open-source e-commerce demo) with Page Object Model, parametrized edge cases, CI badge, and zero hardcoded `sleep()` calls. Interviews test coding fundamentals (strings/arrays), writing test cases on the spot ("test an ATM or UPI payment flow"), flaky test debugging, and HTTP/SQL queries.

## Adjacent Roles & Trade-Offs
- **Backend / Full-Stack Engineer:** Many SDETs transition into feature engineering within 1–2 years because they already master Git, APIs, SQL, and CI/CD.
- **DevOps / Release Engineer:** Focuses more on CI pipelines, Docker, and release reliability.
- **Cybersecurity AppSec:** Natural pivot from negative/edge-case API testing into OWASP security testing.
