# Diet App Backend

This is the backend service for a diet and fitness application i made with a friend and we stopped athe the backend. It provides APIs to manage users, calculate BMI, and interact with a PostgreSQL database, built with Flask and Docker.

## Features

- User Management (Add/Edit/Delete Users)
- BMI Calculation
- PostgreSQL Database Integration
- Dockerized Deployment

## Technologies

- **Backend Framework**: Flask
- **Database**: PostgreSQL
- **Containerization**: Docker, Docker Compose

## Setup and Installation

### Prerequisites

- Docker and Docker Compose installed
- Python 3.x installed (for local development)


### AI Configuration

The AI powered endpoints rely on environment variables so the service can be configured without
code changes. Set the following variables in your shell, Docker Compose file, or deployment
platform before starting the API:

- `AI_API_KEY` – Secret key used to authenticate against the AI provider. Required for any
  AI-powered endpoints to function.
- `AI_MODEL_NAME` – Identifier of the model to use (for example `gpt-4o-mini`). Defaults to a
  lightweight model suitable for testing.
- `AI_BASE_URL` – Optional base URL for the AI provider if it differs from the default.
- `AI_PROMPT_TEMPLATE_DIET` – Optional custom template for the diet plan prompt. The template can
  reference `{user_name}`, `{goal}`, and `{metrics}` placeholders.
- `AI_PROMPT_TEMPLATE_WORKOUT` – Optional custom template for workout plans with the same
  placeholders.
- `AI_PROMPT_TEMPLATE_CHAT` – Optional template for conversational prompts. Placeholders include
  `{user_name}`, `{history}`, and `{message}`.

When running the automated tests, placeholder values are injected automatically so the suite can
stub the AI client without reaching an external service.



## Running Tests

1. Install application dependencies:
   ```bash
   pip install -r api/requirements.txt
   ```
2. Install test dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Run the automated test suite:
   ```bash
   pytest
   ```
