# SmartSeminarian Backend

This repository contains the backend for the SmartSeminarian application, a learning platform that helps users create personalized learning paths and explore concepts.

## Table of Contents

- [Setup Instructions](#setup-instructions)
- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [API Documentation](#api-documentation)
- [Dependencies](#dependencies)
- [Configuration](#configuration)

## Setup Instructions

To set up and run the backend, follow these steps:

### 1. Initialize Environment Variables

```bash
./init-local-env.sh
```

This script will:
- Extract git information (branch, repo, commit SHA)
- Create a `.env` file with necessary environment variables
- Set up Memgraph connection details
- Prompt you to enter your OpenAI API key (required for AI features)
- Create a data directory
- Copy the docker-compose.yml from the deploy directory to the root

### 2. Build the Docker Image

```bash
./build-local-image.sh
```

This script builds a Docker image for the backend service with the appropriate tag.

### 3. Start the Containers

```bash
docker compose up
```

This command starts three containers:
- **memgraph**: A graph database service (accessible at ports 7687, 3000, and 7444)
- **service**: The main backend service (accessible at port 5050)
- **test**: A test container that runs test_dashboard.py (accessible at port 5001)

## Project Overview

SmartSeminarian is a learning platform that helps users create personalized learning paths based on their goals. The backend provides the following core features:

- **User Authentication**: GitHub-based authentication system
- **Concept Management**: Create, update, delete, and explore learning concepts
- **Learning Path Generation**: AI-powered generation of learning paths based on user goals
- **Knowledge Tracking**: Track user mastery of different concepts
- **AI Assistant**: Chat with an AI tutor for help with learning

## Architecture

The backend is built with the following components:

- **Flask**: Web framework for the API
- **SQLAlchemy**: ORM for relational data (users, sessions, problems)
- **Memgraph**: Graph database for storing concepts and learning paths
- **OpenAI**: AI services for generating learning paths and providing tutoring

The application uses a microservices architecture with three main services:
1. **Backend Service**: The main API service
2. **Memgraph**: Graph database for storing the knowledge graph
3. **Test Service**: For testing and demonstration

## API Documentation

The API documentation is available at `/api/docs` when the service is running. Here are the main endpoints:

### Authentication
- `POST /login`: Authenticate with GitHub username and token

### Concepts
- `GET /concept`: Get all concepts
- `POST /concept`: Create a new concept
- `GET /concept/<concept_id>`: Get a specific concept
- `PUT /concept/<concept_id>`: Update a concept
- `DELETE /concept/<concept_id>`: Delete a concept
- `GET /concept/<concept_id>/content`: Get content for a concept (explanation, analogy, quiz)
- `POST /concept/explore`: Explore a concept in depth

### Learning Paths
- `POST /learning-path/generate`: Generate a learning path based on a goal
- `GET /learning-path`: Get all learning paths
- `GET /learning-path/<path_id>`: Get a specific learning path
- `DELETE /learning-path/<path_id>`: Delete a learning path

### Knowledge Tracking
- `POST /concept/<concept_id>/mastery`: Update mastery level for a concept

### Chat
- `POST /chat`: Chat with the AI tutor

## Dependencies

The backend depends on the following main packages:
- Flask and related packages (flask_sqlalchemy, flask_swagger_ui, flask_cors)
- gunicorn for serving the application
- python-dotenv for environment variable management
- phidata and duckduckgo-search for AI assistant functionality
- openai for OpenAI API integration
- gqlalchemy for Memgraph integration

See `app/requirements.txt` for the complete list.

## Configuration

Configuration is managed through environment variables, which are set up by the `init-local-env.sh` script. The main configuration options include:

- **OPENAI_API_KEY**: Your OpenAI API key (required for AI features)
- **MEMGRAPH_HOST**: Hostname for the Memgraph database (default: memgraph)
- **MEMGRAPH_PORT**: Port for the Memgraph database (default: 7687)

Additional configuration options can be found in the `.env` file after running `init-local-env.sh`.
