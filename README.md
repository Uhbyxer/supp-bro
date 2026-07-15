# SuppBro

SuppBro is an assistant for support teams that helps triage and troubleshoot project issues with the right product context.

Support engineers often need to understand more than the ticket itself: which feature is affected, where the documentation lives, who owns the area, what recent changes may be related, and what troubleshooting steps are already known. SuppBro is intended to bring that context together so support teams can move from issue report to informed next action faster.

## Goals

- Help support teams triage incoming project issues.
- Surface relevant feature context, documentation, owners, and stakeholders.
- Suggest likely troubleshooting paths based on known product information.
- Reduce repeated manual searching across docs, tickets, chats, and project history.
- Improve handoffs between support, engineering, product, and customer-facing teams.

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
