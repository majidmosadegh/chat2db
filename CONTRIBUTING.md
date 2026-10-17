# Contributing to chat2db

Thanks for your interest in helping chat2db grow.

The project is early-stage and is looking for people who can help understand the existing implementation, improve its reliability, and shape its future direction. You do not need permission from the original creator to start a constructive discussion.

## Before you start

- Read the README and inspect the current code before assuming a feature is supported.
- Treat the project as experimental until its setup, security model, and behavior have been verified.
- Never commit credentials, database dumps, customer data, API keys, encryption keys, or other secrets.
- Do not test against production or sensitive databases.

## Ways to contribute

- Report reproducible bugs or confusing behavior.
- Improve setup instructions, architecture documentation, and examples.
- Add or improve tests.
- Review database access, SQL generation, and query-execution safety.
- Propose focused product or UX improvements.
- Help maintain the project or discuss a longer-term role.

## Issues

When opening an issue, include as much of the following as applies:

- What you expected to happen.
- What actually happened.
- Steps to reproduce the problem.
- Relevant logs or screenshots, with secrets and personal data removed.
- Your environment and the version or commit you tested.

For feature proposals, explain the problem first, the proposed approach, and any trade-offs.

## Pull requests

1. For substantial changes, open an issue first to discuss the approach.
2. Keep pull requests focused and explain the reason for the change.
3. Add or update tests and documentation where relevant.
4. Describe how you validated the change. If you could not run tests, say so.
5. Never include real credentials, sensitive data, or unrelated formatting churn.

The repository may not yet have a complete automated test or release workflow. Please document the checks you were able to perform rather than assuming they exist.

## Architecture and roadmap

The project did not start with LangChain as its core architecture. That is part of its history, not a rule that contributors must preserve at all costs. Proposals to keep, replace, or introduce frameworks are welcome when supported by clear requirements, trade-offs, and discussion.

## Maintainers and collaboration

The original creator currently has limited time to lead active development. Contributors interested in taking on ongoing responsibility, helping set priorities, or becoming maintainers are especially welcome. Please open an issue to introduce yourself and describe the area you would like to help with.

## License status

This project is released under the MIT License. See LICENSE.
