# AI Code Review Setup

This project uses **PR-Agent** for automated AI code reviews when creating Pull Requests.

## Features

- Automatic code review upon PR creation or update
- Code quality scoring and assessments
- Actionable code improvement suggestions
- Security vulnerability checks
- Test coverage evaluation
- Automatic PR description generation
- Slash-command interactions via comments

## Setup

### 1. Add OpenAI / Anthropic API Key to GitHub Secrets

1. Navigate to: `Settings` → `Secrets and variables` → `Actions`
2. Click `New repository secret`
3. Add:
   - Name: `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`)
   - Value: Your API key

### 2. Configuration (Optional)

The `.pr_agent.toml` file contains optimal settings for the project. You can customize:
- Number of suggestions
- Review focus areas (security, tests, performance)
- Model selection (e.g. GPT-4o, Claude 3.5 Sonnet)

## Usage

### Automatic Review
PR-Agent automatically reviews when:
- A new PR is opened
- New commits are pushed to an open PR
- A PR is reopened

### Slash Commands
Comment on any PR with the following commands:
- `/describe`: Generate or update PR description
- `/review`: Run a comprehensive code review
- `/improve`: Suggest code improvements
- `/ask <question>`: Ask a question about the changes
