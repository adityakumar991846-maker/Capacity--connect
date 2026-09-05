# Capacity Connect

Capacity Connect is an enterprise-grade digital learning, certification, and vocational governance platform designed for scalable capacity building. It connects trainees, trainers, and platform administrators within a unified ecosystem powered by a **Django REST Framework (DRF)** backend, a responsive Bootstrap 5 frontend, and a secure **Supabase Authentication & JWT** architecture.

---

## 1. User Roles

The platform provides role-based access control (RBAC) across three primary user roles:

*   **Trainee**: Discovers and enrolls in courses, completes modular curriculum subjects, submits assignments, engages in module discussions, rates and reviews courses, and earns cryptographically verifiable digital certificates upon course completion.
*   **Trainer**: Designs, builds, and submits courses with modular syllabi; creates quizzes and assignments; grades trainee submissions; oversees course rosters; and tracks trainee completion analytics.
*   **Administrator**: Manages platform governance through a custom website Admin Dashboard; reviews, approves, rejects, or archives courses; oversees user accounts; monitors platform-wide enrollments, pass rates, and assessments; governs certificates (issuance, revocation, reinstatement); and analyzes student placement readiness.

---

## 2. Key Features

*   **Trainee Dashboard**: Centralized hub displaying active enrollments, course progress bars, recent achievements, and quick navigation to resume learning.
*   **Trainer Dashboard**: Course creation studio, curriculum builder, trainee roster monitoring, and teaching analytics.
*   **Custom Admin Dashboard (`admin-dashboard.html`)**: Production-ready platform oversight center featuring 7 live KPI cards (Total Users, Trainers, Trainees, Courses, Enrollments, Average Completion Rate, and Pending Approvals with quick-filtering), full user management, assessment oversight, certificate governance, and career readiness funnel analytics.
*   **Course & Curriculum Management**: Comprehensive course drafting, syllabus module ordering, prerequisites, duration tracking, and structured approval workflows (`DRAFT` $\rightarrow$ `PUBLISHED` / `REJECTED` / `ARCHIVED`).
*   **Enrollment & Learning Tracking**: Real-time progress tracking calculation per subject module completion with completion dates.
*   **Assessments & Quizzes**: Multiple-choice assessment questions, timed attempts, scoring algorithms, and pass/fail tracking.
*   **Assignments & Review Engine**: File attachment submissions, trainer scoring rubrics, and feedback loops.
*   **Course Discussions**: Module-specific Q&A threads between trainees and instructors.
*   **Ratings & Reviews**: Trainee course ratings and verified reviews.
*   **Digital Certificates & Public Verification**: Auto-generated credentials with unique verification codes (`CC-YYYY-XXXX-XXXX`) and SHA-256 cryptographic hashes, supporting public, anonymous instant verification.
*   **Platform Analytics**: Multi-step completion funnels, category distribution, top-performing courses, and career/placement readiness by honors tier (Distinction, Merit, Pass).
*   **Enterprise Security**: Cryptographic JWT signature verification, PyJWT clock skew tolerance, DRF API throttling, CORS/CSRF protections, and strict role sanitization.

---

## 3. System Requirements

*   **Python**: Version `3.10+` (developed and tested on Python `3.13.2`)
*   **Database**: MySQL Server `8.0+` (or MariaDB `10.5+`)
*   **Git**: Version `2.30+`
*   **Web Browser**: Any modern browser (Chrome, Firefox, Edge, Safari)
*   **Code Editor**: VS Code (recommended) or any preferred IDE

---

## 4. Repository Setup

Clone the repository to your local workstation:

```powershell
git clone https://github.com/adityakumar991846-maker/Capacity--connect.git
cd Capacity--connect
```

---

## 5. Backend Setup

### Step 1: Create and Activate Virtual Environment

On Windows (PowerShell):

```powershell
python -m venv backend\venv
backend\venv\Scripts\Activate.ps1
```

*(If script execution is disabled on PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

On macOS / Linux:

```bash
python3 -m venv backend/venv
source backend/venv/bin/activate
```

### Step 2: Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

### Step 3: Environment Configuration (`backend/.env`)

The `backend/.env` file contains environment-specific settings and is **intentionally excluded from Git** for security. Create your local configuration file from the template:

```powershell
copy backend\.env.example backend\.env
```

Open `backend/.env` in your editor and configure the following parameters:

| Variable | Description | Example / Default |
|---|---|---|
| `SECRET_KEY` | Django cryptographic signing secret | Generate a random 50+ character string |
| `DEBUG` | Development mode flag | `True` (for local development) |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames | `localhost,127.0.0.1` |
| `DB_NAME` | Local MySQL database name | `capacity_connect` |
| `DB_USER` | MySQL database user | `root` |
| `DB_PASSWORD` | MySQL database user password | Your local database password |
| `DB_HOST` | MySQL host address | `127.0.0.1` |
| `DB_PORT` | MySQL connection port | `3306` |
| `SUPABASE_URL` | Base URL of the Supabase project | Provided by project lead (e.g. `https://<project-id>.supabase.co`) |
| `SUPABASE_JWT_SECRET` | Secret key for HS256 JWT decoding | Provided by project lead |
| `DEFAULT_FILE_STORAGE_BACKEND` | Storage backend for media files | `filesystem` (local development default) |

> [!CAUTION]
> Never commit `backend/.env` to Git. Never share database passwords or the Supabase service-role key.

### Step 4: Run Database Migrations

Ensure your local MySQL service is running and the database exists:

```powershell
backend\venv\Scripts\python backend\manage.py migrate
```

---

## 6. Frontend Setup

### Step 1: Configure Supabase Client (`frontend/js/supabase-config.js`)

The frontend configuration file `frontend/js/supabase-config.js` is **intentionally excluded from Git**. Create your local copy from the example template:

```powershell
copy frontend\js\supabase-config.example.js frontend\js\supabase-config.js
```

Open `frontend/js/supabase-config.js` and set the public Supabase project credentials:

```javascript
window.__SUPABASE_URL__ = 'https://<your-project-id>.supabase.co';
window.__SUPABASE_ANON_KEY__ = '<your-public-anon-key>';
```

> [!NOTE]
> The Supabase **Anon Key** is a safe, public client-side key intended for browser use. **NEVER** place the Supabase `service_role` key or JWT secret in frontend code.

---

## 7. Running the Application

To run the complete platform locally, start both the backend API server and the frontend static HTTP server concurrently.

### Terminal 1: Run Django Backend (Port 8000)

From the project root:

```powershell
backend\venv\Scripts\python backend\manage.py runserver 127.0.0.1:8000
```

The Django REST API will be accessible at: `http://127.0.0.1:8000/api/`

### Terminal 2: Run Frontend Server (Port 5500)

Open a second terminal in the project root and start the built-in HTTP server:

```powershell
backend\venv\Scripts\python -m http.server 5500 -d frontend
```

The Capacity Connect website will be accessible at: `http://127.0.0.1:5500/`

---

## 8. Platform URLs & Routing

| Destination | Local URL | Purpose |
|---|---|---|
| **Landing Page** | `http://127.0.0.1:5500/index.html` | Public landing page and course highlights |
| **Login Page** | `http://127.0.0.1:5500/pages/login.html` | Authentication portal for all roles |
| **Registration Page** | `http://127.0.0.1:5500/pages/register.html` | Public signup (Trainee or Trainer) |
| **Role Dashboard Router** | `http://127.0.0.1:5500/pages/dashboard.html` | Automatic redirect to user's role dashboard |
| **Admin Dashboard** | `http://127.0.0.1:5500/pages/admin-dashboard.html` | Custom website platform management hub |
| **Trainer Dashboard** | `http://127.0.0.1:5500/pages/trainer-dashboard.html` | Course studio, rosters, and teaching tools |
| **Trainee Dashboard** | `http://127.0.0.1:5500/pages/trainee-dashboard.html` | Learning hub and course progress |
| **Course Catalog** | `http://127.0.0.1:5500/pages/browse-courses.html` | Public published courses catalog |
| **Certificate Verification** | `http://127.0.0.1:5500/pages/verify-certificate.html` | Public instant credential verification |
| **Django Developer Admin** | `http://127.0.0.1:8000/admin/` | Low-level developer / database administration |
| **Backend API Base** | `http://127.0.0.1:8000/api/` | REST API root |

---

## 9. Authentication Architecture

Capacity Connect uses a hybrid **Supabase Auth + Django RBAC** architecture:

1. **Client Authentication**: When a user submits credentials on `/pages/login.html`, the browser communicates directly with the Supabase Auth API (`signInWithPassword`).
2. **Token Handshake**: Supabase returns a cryptographically signed JWT access token containing the user's Supabase UUID (`sub`).
3. **Identity Verification & Role Resolution**:
   - The frontend calls `GET /api/auth/me/` with `Authorization: Bearer <token>`.
   - Django's `SupabaseAuthentication` backend cryptographically verifies the token using the Supabase JWKS public keys (or `SUPABASE_JWT_SECRET`).
   - Django looks up the user's `UserProfile` matching the `supabase_uid`.
   - Django authoritatively responds with the user's identity and assigned role (`ADMIN`, `TRAINER`, or `TRAINEE`).
4. **Privilege Escalation Protection**: Public registration through `/pages/register.html` strictly restricts role selection to `TRAINEE` or `TRAINER`. The `ADMIN` role can never be claimed through public registration and must be designated directly in the backend.

---

## 10. Test Accounts & Testing Credentials

For security reasons, live credentials are not stored in the repository. When testing the platform locally:

*   **Trainee / Trainer**: You can create new Trainee and Trainer accounts directly using the public registration page at `http://127.0.0.1:5500/pages/register.html`.
*   **Pre-Configured Test Accounts**: Obtain the authorized credentials for the standard test accounts from your project administrator:
    *   **Admin Account**: `live_admin@example.com` (assigned `ADMIN` role)
    *   **Trainer Account**: `live_trainer@example.com` (assigned `TRAINER` role)
    *   **Trainee Account**: `live_trainee@example.com` (assigned `TRAINEE` role)
*   **Linking an Existing Django User to Supabase**:
    If you create a Django user manually via `createsuperuser` or the Django shell, link their account to their Supabase user UUID using the management command:
    ```powershell
    backend\venv\Scripts\python backend\manage.py link_supabase_user --email <user-email> --supabase-uid <supabase-user-uuid>
    ```

---

## 11. Testing the Admin Dashboard

1. Navigate to `http://127.0.0.1:5500/pages/login.html`.
2. Sign in with the authorized Admin account (`live_admin@example.com`).
3. The application will automatically authenticate, verify the `ADMIN` role with Django, and redirect directly to `frontend/pages/admin-dashboard.html`.
4. **Features Available to Test**:
   *   **Platform Overview**: View the 7 live KPI cards. Click the "Pending Approvals" badge to instantly filter courses awaiting review.
   *   **Course Management**: Filter courses by status (`All`, `Draft`, `Published`, `Rejected`, `Archived`) or search by course title.
   *   **Course Inspection**: Click "Details" to open the Course Inspection Modal (`#courseDetailModal`) and inspect the full curriculum and objectives.
   *   **Approval & Rejection**: Click "Publish" to approve a course, or click "Reject" to open the Rejection Modal and submit required feedback.
   *   **User Management**: View the platform user roster, filter by role, inspect user details, and toggle account activation status.
   *   **Assessments Tab**: Review assessment pass rates, total question counts, and submission attempt statistics.
   *   **Certificates Governance**: Search platform certificates by code or student name, click "Revoke" to invalidate credentials with audit notes, or click "Reinstate" to restore validity.
   *   **Platform Analytics**: Review the enrollment conversion funnel, category distribution bars, top 5 performing courses, and certified graduate placement readiness.

---

## 12. Recommended End-to-End Test Workflow

To verify complete end-to-end platform integrity:

1. **Course Creation**: Log in as a Trainer $\rightarrow$ create a new course with at least one syllabus module $\rightarrow$ verify status is `DRAFT`.
2. **Trainer Dashboard**: Verify the course appears under "My Courses" and metrics update.
3. **Course Rejection**: Log in as Admin $\rightarrow$ open Admin Dashboard $\rightarrow$ reject the course with feedback $\rightarrow$ verify course status is `REJECTED` and reason is visible to the trainer.
4. **Course Approval**: Log in as Admin $\rightarrow$ click "Publish" on the draft course $\rightarrow$ verify course status transitions to `PUBLISHED`.
5. **Catalog Visibility**: Log in as a Trainee $\rightarrow$ visit `/pages/browse-courses.html` $\rightarrow$ confirm the published course is visible.
6. **Enrollment & Progress**: Enroll in the course $\rightarrow$ open Trainee Dashboard $\rightarrow$ verify enrollment appears with progress tracking.
7. **Certificates**: Complete curriculum modules and assessments $\rightarrow$ claim digital certificate $\rightarrow$ view certificate in `/pages/my-certificates.html`.
8. **Public Verification**: Copy the certificate code (e.g. `CC-2026-XXXX-XXXX`) or hash $\rightarrow$ open `/pages/verify-certificate.html` in an Incognito window (unauthenticated) $\rightarrow$ verify credential status displays `VALID`.
9. **Certificate Governance**: Log in as Admin $\rightarrow$ revoke the certificate $\rightarrow$ re-verify in Incognito to confirm status displays `REVOKED` $\rightarrow$ reinstate certificate from Admin Dashboard $\rightarrow$ confirm status displays `VALID`.
10. **RBAC Guard**: Log in as Trainee or Trainer and attempt to navigate directly to `/pages/admin-dashboard.html` $\rightarrow$ verify access is denied and redirected safely.

---

## 13. Running Automated Tests & Checks

### Django System Check

Verify system settings, model relationships, and deployment readiness:

```powershell
backend\venv\Scripts\python backend\manage.py check
```

*(Expected output: `System check identified no issues (0 silenced).`)*

### Full Regression Test Suite

Run the complete 240-test regression suite covering all backend apps:

```powershell
backend\venv\Scripts\python backend\manage.py test core certificates courses enrollments assessments discussions assignments reviews
```

*(Expected output: `Ran 240 tests in ... OK`)*

---

## 14. Troubleshooting

*   **`Supabase Auth client not initialized` / Blank Config**:
    Ensure you created `frontend/js/supabase-config.js` from `frontend/js/supabase-config.example.js` and that `window.__SUPABASE_URL__` and `window.__SUPABASE_ANON_KEY__` are properly populated.
*   **Port 8000 Already in Use**:
    Terminate the conflicting process or run Django on an alternate port (e.g. `runserver 127.0.0.1:8080`). If changing ports, set `window.__API_BASE_URL__ = 'http://127.0.0.1:8080/api'` in the browser console.
*   **Port 5500 Already in Use**:
    Run the Python HTTP server on an available port: `python -m http.server 5501 -d frontend`.
*   **`Invalid login credentials`**:
    Verify that the test user exists in both the Supabase Authentication user pool and the Django database. If you created a user directly in Django, link their account using `python backend\manage.py link_supabase_user`.
*   **`Invalid token: The token is not yet valid (iat)`**:
    This indicates minor clock synchronization drift between your local system clock and Supabase's cloud servers. Ensure `leeway=60` is present in `backend/core/authentication.py` (configured by default).
*   **Missing Python Packages**:
    Ensure the virtual environment is activated (`(venv)` shown in terminal) before running `pip install -r backend\requirements.txt`.

---

## 15. Repository Structure

```text
Capacity--connect/
├── .gitignore                          # Git exclusions (credentials, venv, media, static)
├── Procfile                            # Production deployment process definition
├── README.md                           # Platform setup and testing documentation
├── backend/
│   ├── .env.example                    # Environment variables template
│   ├── manage.py                       # Django management utility
│   ├── requirements.txt                # Python package dependencies
│   ├── assessments/                    # Quizzes, questions, attempts, and admin stats
│   ├── assignments/                    # File submissions, rubrics, and grading
│   ├── certificates/                   # Digital certificates and public verification
│   ├── config/                         # Django settings, WSGI/ASGI, and URL routing
│   ├── core/                           # Supabase auth, user profiles, RBAC, and storage
│   ├── courses/                        # Course catalog, curriculum, and admin analytics
│   ├── discussions/                    # Module Q&A discussion threads
│   ├── enrollments/                    # Trainee course enrollment and progress tracking
│   └── reviews/                        # Course ratings and student reviews
└── frontend/
    ├── index.html                      # Platform landing page
    ├── css/
    │   ├── dashboard.css               # Role dashboard styling
    │   └── styles.css                  # Platform design system
    ├── js/
    │   ├── admin-dashboard.js          # Custom Admin Dashboard controller
    │   ├── app.js                      # Central API client and Supabase token injector
    │   ├── auth.js                     # Authentication state and route guards
    │   ├── dashboard.js                # Role dashboard layout and navigation controller
    │   ├── supabase-client.js          # Supabase Auth SDK wrapper
    │   ├── supabase-config.example.js  # Public Supabase credentials template
    │   ├── trainer-dashboard.js        # Trainer studio and roster controller
    │   └── verify-certificate.js       # Public credential verification controller
    └── pages/
        ├── admin-dashboard.html        # Custom Admin Dashboard web interface
        ├── browse-courses.html         # Course catalog
        ├── course-details.html         # Course overview and syllabus preview
        ├── course-learn.html           # Interactive learning player
        ├── dashboard.html              # Dynamic role-based dashboard router
        ├── login.html                  # Universal login interface
        ├── my-certificates.html        # Trainee credential portfolio
        ├── my-courses.html             # Trainee enrolled courses overview
        ├── register.html               # Universal user registration interface
        ├── trainee-dashboard.html      # Trainee learning dashboard
        ├── trainer-dashboard.html      # Trainer course studio dashboard
        └── verify-certificate.html     # Public certificate verification interface
```

---

## 16. Security Guidelines

1. **Never Commit Secrets**: `backend/.env` and `frontend/js/supabase-config.js` are ignored by `.gitignore`. Never use `git add -f` to force-stage them.
2. **Credential Confidentiality**: Never share the database root password, Supabase `service_role` private key, or Django `SECRET_KEY` in emails, tickets, or pull requests.
3. **Public Keys Only on Frontend**: Only the Supabase `anon` key should ever be configured in frontend JavaScript.
4. **Git Contribution Policy**: Testers and teammates should clone the repository and create separate feature branches. Do not push directly to the `main` branch without code review and approval.
