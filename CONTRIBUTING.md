# Contributing to the Hytale Modding Community Discord Bot

Thank you for your interest in contributing to the Hytale Community Discord Bot!
This bot is a community-driven project built to support and enhance the Hytale Modding Discord server through helpful commands, integrations, and automation.
We welcome contributions from developers of all skill levels.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Setting up a Development Environment](#setting-up-a-development-environment)
- [Submitting Changes](#submitting-changes)
- [Community](#community)
- [Questions?](#questions)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## How Can I Contribute?

### Submitting Issues

You can help by submitting issues for:
- **Bug Reports**: Incorrect or unexpected behavior of commands or features, or other problems
- **Feature Requests:** New commands, integrations, automations, or improvements to existing features

When opening an issue, please use a clear title, provide relevant details, include screenshots when helpful, and follow the appropriate issue template.

### Contributing Code

Before contributing code, open an issue if one does not exist already and get yourself assigned before starting.
If someone is already assigned, and you want to work on or expand the issue, coordinate with them first.
When submitting a pull request, make sure the related issue is tagged correctly. You can read more about this under [Submitting Changes](#submitting-changes).

## Setting up a Development Environment

### Prerequisites

- Git
- An IDE or text editor (PyCharm, VS Code, etc.)
- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/) Python package and project manager
- A Discord bot application and a test server for development and testing
- Access to a MySQL database

### Local Development Setup

1. Fork the repository on GitHub.
2. Clone your fork, rename the root directory if you like, and enter the directory.
3. Install dependencies:
    ```bash
    uv sync
    ```
4. Copy `.env.example` to `.env` and configure the required environment variables:
    - A Discord bot token (TOKEN)
    - Database connection variables (see the settings module for details)
5. Start the bot:
    ```bash
    uv run main.py
    ```
6. Fill out all required values of the generated `config_template.json` and copy it to `config.json` before restarting the bot when starting it for the first time.
    - When running the bot with docker, make sure to mount the root directory to the docker working directory with `-v /<path-to-robot>:/app`
   
## Submitting Changes

> [!IMPORTANT]
> This project uses Conventional Commits. It is a specification that defines a consistent structure for commit messages and ensures a clear, machine-readable commit history. It is recommended that you [read the specification](https://www.conventionalcommits.org), which also includes examples and an FAQ.

### Branch Workflow

Before contributing, make sure your fork is up to date by syncing it on GitHub and pulling the latest changes locally.
Create a new branch in your fork with a clear, descriptive name for the issue you are working on, then implement your changes.
Commit and push your work. Split your work into multiple commits if there are a lot of changes that conform to multiple Conventional Commit types.
Once everything is tested and working, open a pull reqeust and follow the guidelines mentioned below.

### Commit Messages

When writing a commit message, follow these conventions:
- Structure the message according to the Conventional Commits specification
- Use present tense: "Add feature" not "Added feature"
- Use imperative mood: "Fix bug" not "Fixes bug"
- Keep first line under 72 characters
- Use the optional body to add detail or context if needed

### Pull Requests

When opening a pull request:
- Tag the related issue in the title using the correct format:
    ```
    GH-<issue-number>: Title

    Example:
    GH-37: Add auto-thread command
    ```
- Explain what you changed, why you changed it (if helpful), and note anything reviewers should pay attention to in particular
- Test your changes before submitting the pull request

## Community

Join our [Discord server](https://discord.gg/54WX832HBM) for real-time help and discussions! Contributors may also claim a role, recognizing their help to the community.

## Questions?

If you have any questions not covered in this contributing guide, feel free to ask in the Discord server or to reach out to a project maintainer.

Thank you for contributing to the Hytale Modding Discord Bot!