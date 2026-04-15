# NexaFi User Service

This service handles user authentication, authorization, and profile management for the NexaFi platform.

## Setup and Installation

### Prerequisites

- Python 3.9+
- PostgreSQL or SQLite (as configured in `.env`)

### 1. Create and Activate Virtual Environment

It is highly recommended to use a virtual environment to isolate dependencies.

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configuration

Copy the example environment file and fill in your configuration details.

```bash
cp .env.example .env
# Edit .env with your settings
```

**Required Environment Variables in `.env`:**

- `SECRET_KEY`: A long, random string for token signing.
- `DATABASE_URL`: Connection string for your database (e.g., `sqlite:///./data/users.db`).
- `DEBUG`: `True` or `False`.

## Running the Service

### Development Mode

The service can be run directly using Python:

```bash
python3 src/main.py
```

### Production (using Gunicorn)

For production deployment, use a WSGI server like Gunicorn:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 src.main:app
```

## API Endpoints

The service exposes endpoints under `/api/v1/auth` and `/api/v1/users`. Refer to the code in `src/routes/user.py` for details.
