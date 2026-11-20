# DevOps & Cloud Engineer Career Guide (India Freshers)

## Role Overview
DevOps, Site Reliability (SRE), and Cloud Engineers automate builds, deployments, infrastructure provisioning, monitoring, and incident recovery so software runs fast and reliably at scale. Demand is steady across SaaS startups, cloud consultancies, and enterprises in Bengaluru, Pune, Hyderabad, Noida, Gurugram, and remote teams. Typical fresher pay ranges from INR 40,000 to 1,05,000/month (internships INR 18,000 to 40,000/month).

## Core Skills & Prerequisites
Core pillars are Linux administration (systemd, networking, permissions, shell scripting), Git, Docker (multi-stage builds, networking, security), CI/CD pipelines (GitHub Actions or GitLab CI), one major cloud provider (AWS is most common in India — IAM, VPC, EC2, S3, RDS, ECR), Infrastructure as Code (Terraform), Kubernetes fundamentals, and observability (Prometheus, Grafana, structured logs). Python or Bash scripting ties everything together.

## 4-Week Learning Roadmap
- **Week 1 — Linux, Networking & Shell Automation:** Practice Linux processes, SSH, DNS, reverse proxies (Nginx), firewall basics, and Bash/Python automation scripts. Deliverable: an automated server health & backup script with clean exit codes and logging.
- **Week 2 — Docker & CI/CD Pipelines:** Containerize a multi-service web app (API + Postgres) with non-root multi-stage Dockerfiles, healthchecks, and Docker Compose. Wire GitHub Actions to lint, test, scan, and build images on every push. Deliverable: reproducible repo with passing CI badge.
- **Week 3 — Cloud (AWS Free Tier) & Terraform:** Provision a VPC, security groups, S3 bucket, and compute instance declaratively using Terraform with remote state best practices (always tear down resources after labs to avoid billing). Deliverable: modular Terraform repo + architecture diagram.
- **Week 4 — Kubernetes & Observability:** Deploy the containerized app to local Kind/Minikube with Deployments, Services, ConfigMaps, liveness/readiness probes, and Prometheus/Grafana dashboards. Deliverable: K8s manifests + screenshot of live latency/error-rate dashboard.

## Free Courses & Resources
- **KodeKloud Free Courses & Docker/K8s Labs** (https://kodekloud.com/free-labs): Hands-on browser labs for Linux, Docker, and Kubernetes.
- **MIT Missing Semester** (https://missing.csail.mit.edu): Essential shell, tooling, and Linux fluency.
- **HashiCorp Terraform Tutorials** (https://developer.hashicorp.com/terraform/tutorials): Official IaC walkthroughs.
- **AWS Skill Builder Free Tier** (https://skillbuilder.aws): Official cloud practitioner and solutions architect foundations.
- **Kubernetes Official Interactive Tutorials** (https://kubernetes.io/docs/tutorials/): Authoritative cluster concepts.

## Portfolio Projects & Interview Prep
Deploy a real open-source or personal API end-to-end with zero manual clicking: Terraform creates infra, GitHub Actions runs tests and builds a slim non-root Docker image, and Grafana monitors `/health` and latency. Interviews focus on Linux troubleshooting ("a service returns 502 — walk me through debugging"), Docker layers vs VMs, CI/CD design, IAM least privilege, and Kubernetes Pod lifecycle.

## Adjacent Roles & Trade-Offs
- **Backend Engineer:** More time writing product business logic and SQL, less time on infrastructure and on-call operations.
- **MLOps Engineer:** Applies Docker, CI/CD, and cloud pipelines specifically to ML training, model registries, and inference serving.
- **Cloud Security Engineer:** Deepens AWS IAM, network isolation, container scanning, and DevSecOps compliance.
