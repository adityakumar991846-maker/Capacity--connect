# Capacity Connect — Architecture Overview

## Technology Stack

| Layer       | Technology                          | Version  |
|-------------|-------------------------------------|----------|
| Backend     | Python + Django                     | 6.1      |
| API         | Django REST Framework               | 3.18.0   |
| Database    | MySQL                               | 8.x+     |
| Frontend    | HTML / CSS / JavaScript + Bootstrap | 5.3.3    |
| CORS        | django-cors-headers                 | 4.9.0    |
| Environment | python-dotenv                       | 1.2.3    |

## Project Structure

```
Capacity--connect/
├── backend/                    # Django project root
│   ├── config/                 # Django project configuration
│   │   ├── __init__.py
│   │   ├── settings.py         # Main settings (env-driven)
│   │   ├── urls.py             # Root URL configuration
│   │   ├── wsgi.py             # WSGI entry point
│   │   └── asgi.py             # ASGI entry point
│   ├── manage.py               # Django CLI
│   ├── requirements.txt        # Python dependencies
│   ├── .env.example            # Environment variable template
│   └── venv/                   # Python virtual environment (git-ignored)
│
├── frontend/                   # Static frontend
│   ├── index.html              # Landing page
│   ├── pages/                  # Feature-specific HTML pages
│   ├── css/
│   │   └── styles.css          # Custom styles (Bootstrap overrides)
│   ├── js/
│   │   └── app.js              # Core JavaScript + API helper
│   └── assets/                 # Images, icons, fonts
│
├── docs/                       # Project documentation
│   ├── architecture/           # Architecture docs
│   ├── database/               # Database schema docs
│   └── api/                    # API endpoint docs
│
└── .gitignore
```

## Backend Architecture

The backend uses Django's project/app pattern:

- **`config/`** — Project-level configuration (settings, root URLs, WSGI/ASGI).
- **App modules** (to be added) — Each feature (authentication, courses, etc.) will be a separate Django app with its own models, views, serializers, and URLs.

### Settings

All sensitive configuration is loaded from environment variables via `python-dotenv`. See `backend/.env.example` for the full list.

### URL Routing

All API endpoints will live under the `/api/` prefix:

```
/api/auth/      → Authentication (future)
/api/courses/   → Courses (future)
/api/...        → Additional feature APIs
/admin/         → Django admin panel
```

## Frontend Architecture

The frontend is a vanilla HTML/CSS/JS application using Bootstrap 5 for UI components. It communicates with the backend via REST API calls using the `apiRequest()` helper function defined in `js/app.js`.

No frontend build tools, Node.js, or JavaScript frameworks are used. Pages are served as static files.

## Development Workflow

1. **Clone** the repository.
2. **Activate** the virtual environment: `backend\venv\Scripts\activate`
3. **Install** dependencies: `pip install -r backend/requirements.txt`
4. **Configure** environment: Copy `backend/.env.example` to `backend/.env` and fill in values.
5. **Create** the MySQL database: `CREATE DATABASE capacity_connect CHARACTER SET utf8mb4;`
6. **Run migrations**: `python backend/manage.py migrate`
7. **Start** the dev server: `python backend/manage.py runserver`
8. **Open** `frontend/index.html` in a browser (or serve with a local server).

## Security Notes

- `SECRET_KEY` must be regenerated for production.
- `DEBUG` must be `False` in production.
- `CORS_ALLOW_ALL_ORIGINS` is `True` only when `DEBUG=True`. In production, use `CORS_ALLOWED_ORIGINS`.
- `.env` files are git-ignored and must never be committed.
