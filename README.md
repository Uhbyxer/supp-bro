# SuppBro

**SuppBro** is an assistant for support teams that helps triage and troubleshoot project issues with the right product context. The current project scope is related to the [Debezium](https://debezium.io/) open source project and uses Debezium documentation and GitHub project data as the first knowledge sources.

Debezium is a change data capture platform that streams database changes into event-driven systems. Teams use it to keep applications, caches, search indexes, analytics pipelines, and other downstream services in sync with database updates.

Support engineers often need to understand more than the ticket itself: which feature is affected, where the documentation lives, who owns the area, what recent changes may be related, and what troubleshooting steps are already known. **SuppBro** is intended to bring that context together so support teams can move from issue report to informed next action faster.

## Goals

- Help support teams triage incoming project issues.
- Surface relevant feature context, documentation, owners, and stakeholders.
- Suggest likely troubleshooting paths based on known product information.
- Reduce repeated manual searching across docs, tickets, chats, and project history.
- Improve handoffs between support, engineering, product, and customer-facing teams.

## Debezium Resources

- [Debezium website](https://debezium.io/)
- [Debezium documentation](https://debezium.io/documentation/reference/stable/index.html)
- [Debezium GitHub organization](https://github.com/debezium)
- [Debezium main repository](https://github.com/debezium/debezium)
- [Debezium issue tracker](https://github.com/debezium/dbz/issues)
- [Debezium project board used by this repo](https://github.com/orgs/debezium/projects/5)

## Setup

This project uses Python 3.11, a local virtual environment, `pip`, and `make`.

Run the setup command:

```bash
make setup
```

The command creates `.venv`, upgrades `pip`, and installs dependencies from `requirements.txt`.

Activate the virtual environment before running Python commands:

```bash
source .venv/bin/activate
```

Downloading GitHub project issues requires the GitHub CLI. On macOS, install it with:

```bash
brew install gh
```

Download Debezium project issues into `data/hw1/raw/issues`:

```bash
gh auth login
make download-issues
```
