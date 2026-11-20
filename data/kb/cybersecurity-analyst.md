# Cybersecurity Analyst & AppSec Engineer Career Guide (India Freshers)

## Role Overview
Cybersecurity freshers in India typically enter through two tracks: Security Operations Center (SOC) / Blue Team Analyst (monitoring SIEM alerts, triaging incidents, threat hunting) or Application Security (AppSec) / VAPT Engineer (testing web apps and APIs for OWASP Top 10 vulnerabilities). Hiring hubs include Bengaluru, Pune, Hyderabad, Chennai, Gurugram, and remote MSSPs. Starting fresher compensation ranges from INR 35,000 to 90,000/month (internships INR 15,000 to 35,000/month).

## Core Skills & Prerequisites
Foundations matter more than memorizing tools: TCP/IP networking (DNS, HTTP/TLS, ports, firewalls), Linux command line and permissions, Python or Bash scripting, OWASP Top 10 web vulnerabilities (SQLi, XSS, IDOR, SSRF, broken auth), Burp Suite, Wireshark, Nmap, and SIEM basics (Splunk or Microsoft Sentinel) plus MITRE ATT&CK frameworks.

## 4-Week Learning Roadmap
- **Week 1 — Networking, Linux & Packet Analysis:** Master subnetting, HTTP headers, TLS handshakes, Linux file/process auditing, and Wireshark packet inspection. Deliverable: documented lab write-up analyzing 3 realistic PCAP traffic captures.
- **Week 2 — Web App Security (OWASP Top 10):** Practice exploiting and fixing SQL injection, XSS, CSRF, broken access control, and JWT flaws on authorized labs. Deliverable: 10 solved PortSwigger Web Security Academy labs with clear remediation notes.
- **Week 3 — Defensive Security, SIEM & Log Triage:** Learn Windows/Linux security event logs, brute-force and privilege-escalation detection rules, and incident response playbooks. Deliverable: a home-lab SIEM detection guide or Sigma rule repository on GitHub.
- **Week 4 — Automation Script & Mock VAPT Report:** Write a small Python security utility (e.g., HTTP security header auditor or log anomaly parser) and publish a professional sample VAPT report (on DVWA/Juice Shop) showing executive summary, PoC, CVSS score, and developer fix.

## Free Courses & Resources
- **PortSwigger Web Security Academy** (https://portswigger.net/web-security): The #1 free hands-on training platform for web/API security.
- **TryHackMe Free Rooms (Pre-Security & SOC Level 1 Intro)** (https://tryhackme.com): Guided interactive labs in the browser.
- **Professor Messer Network+ & Security+ Videos** (https://www.professormesser.com): Clear free video series on networking and security fundamentals.
- **OWASP Top 10 & API Security Top 10** (https://owasp.org): Essential industry checklists.
- **LetsDefend Free Tier** (https://letsdefend.io): Realistic simulated SOC alert triage.

## Portfolio Projects & Interview Prep
Never scan or test systems without explicit written permission; always use authorized labs (PortSwigger, OWASP Juice Shop, TryHackMe). In interviews, expect TCP 3-way handshake, HTTPS/TLS flow, how to prevent SQLi/XSS/CSRF, reading a raw HTTP request, and how you would triage a suspicious login alert.

## Adjacent Roles & Trade-Offs
- **DevOps / Cloud Security Engineer:** Combines AWS/Kubernetes/Terraform with IAM and container hardening; higher pay ceiling than L1 SOC.
- **Backend Engineer:** Strong overlap with AppSec — building secure APIs from the start rather than auditing them afterward.
- **QA / SDET:** Shares structured bug reporting and HTTP/API testing skills; often easier fresher entry if security roles are scarce.
