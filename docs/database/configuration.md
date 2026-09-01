# Capacity Connect — Database Configuration

## Database Engine

**MySQL 8.x+** with the `utf8mb4` character set for full Unicode support.

## Connection Configuration

All database credentials are stored in environment variables (never hard-coded):

| Variable      | Description          | Default            |
|---------------|----------------------|--------------------|
| `DB_NAME`     | Database name        | `capacity_connect` |
| `DB_USER`     | MySQL username       | *(empty)*          |
| `DB_PASSWORD` | MySQL password       | *(empty)*          |
| `DB_HOST`     | Database host        | `127.0.0.1`       |
| `DB_PORT`     | Database port        | `3306`             |

These are read in `config/settings.py` via `os.getenv()`.

## Python Driver

The project uses **mysqlclient** (`mysqlclient==2.2.8`), the recommended MySQL adapter for Django.

## Initial Setup

```sql
-- Run in MySQL shell
CREATE DATABASE capacity_connect CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create a dedicated user (recommended for production)
CREATE USER 'cc_user'@'localhost' IDENTIFIED BY 'your-strong-password';
GRANT ALL PRIVILEGES ON capacity_connect.* TO 'cc_user'@'localhost';
FLUSH PRIVILEGES;
```

Then set the credentials in `backend/.env`:

```
DB_NAME=capacity_connect
DB_USER=cc_user
DB_PASSWORD=your-strong-password
DB_HOST=127.0.0.1
DB_PORT=3306
```

## SQL Mode

The Django settings enforce `STRICT_TRANS_TABLES` via the `init_command` option. This ensures data integrity by rejecting invalid or truncated data.

## Schema Management

Django manages the database schema through its migration system:

```bash
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations
```

> **Note:** Business models and the complete schema will be added module by module in subsequent phases.
