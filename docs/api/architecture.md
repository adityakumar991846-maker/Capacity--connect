# Capacity Connect — API Architecture

## Overview

The backend API is built with **Django REST Framework (DRF) 3.18.0** and follows RESTful conventions.

## Base URL

```
http://127.0.0.1:8000/api/
```

All feature APIs will be mounted under the `/api/` prefix.

## Planned API Namespaces

| Namespace            | Module          | Status  |
|----------------------|-----------------|---------|
| `/api/auth/`         | Authentication  | Pending |
| `/api/courses/`      | Courses         | Pending |
| `/api/assessments/`  | Assessments     | Pending |
| `/api/analytics/`    | Analytics       | Pending |
| `/api/certificates/` | Certificates    | Pending |

## DRF Configuration

Configured in `config/settings.py` under `REST_FRAMEWORK`:

| Setting                      | Value                                  |
|------------------------------|----------------------------------------|
| Default Permission           | `IsAuthenticated`                      |
| Pagination                   | `PageNumberPagination` (20 per page)   |
| Renderers                    | JSON + Browsable API                   |

## Authentication

Authentication will be configured in the next phase. The DRF browsable API login/logout is available at `/api-auth/`.

## Response Format

All API responses follow standard DRF conventions:

### Success (single object)
```json
{
    "id": 1,
    "field": "value"
}
```

### Success (paginated list)
```json
{
    "count": 100,
    "next": "http://127.0.0.1:8000/api/resource/?page=2",
    "previous": null,
    "results": [...]
}
```

### Error
```json
{
    "detail": "Error message here."
}
```

## Adding a New API Endpoint

1. Create a new Django app: `python manage.py startapp <app_name>`
2. Add the app to `INSTALLED_APPS` in `config/settings.py`.
3. Create serializers, views, and URL patterns in the app.
4. Include the app's URLs in `config/urls.py` under the `/api/` prefix.

Example in `config/urls.py`:
```python
urlpatterns = [
    path('api/courses/', include('courses.urls')),
]
```

## CORS

- **Development:** All origins are allowed when `DEBUG=True`.
- **Production:** Only origins listed in `CORS_ALLOWED_ORIGINS` are allowed.
