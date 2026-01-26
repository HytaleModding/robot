# Hytale Modding Bot

This bot is used for utility and moderation features for the Hytale Modding Discord.

## Host yourself 

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

### Contributions

All contributions are welcome in the form of PRs linked to an issue. If an issue does not exist already, open one first. For more information about contributing standards in this repository, view the [CONTRIBUTING](/CONTRIBUTING.md) guidelines.