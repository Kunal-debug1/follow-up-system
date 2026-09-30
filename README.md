# 🚀 CRM Follow-Up System

A production-ready, admin-only CRM system designed to manage customer records, import customer spreadsheets, maintain call histories, schedule persistent follow-ups, and manage customer workflows at scale.

The system provides a separate **FastAPI backend** and **React frontend**, with the production application deployed on **Render** and connected to a **MongoDB database**.

---

# 📌 Overview

The CRM Follow-Up System helps sales and support teams manage customer interactions from a centralized dashboard.

It is designed around a simple workflow:

```text
Customer Import
      ↓
Customer Database
      ↓
Call History
      ↓
Follow-Up Scheduling
      ↓
Today / Upcoming / Overdue
      ↓
Customer Management
```

The application is intended for **admin-only CRM operations**, with authentication protecting access to customer and follow-up data.

---

# ✨ Key Features

## 👥 Customer Management

* Customer record management
* Customer contact information
* Customer search
* Customer workflow tracking
* Customer status management

## 📊 Excel / CSV Import

The system supports importing customer data from spreadsheets.

Features include:

* Excel import
* CSV import
* Streaming file processing
* Batch database operations
* Duplicate detection
* Import preview
* Large worksheet safety limits

### Deduplication

Customer records can be identified using:

```text
consumer_number
```

with a fallback based on:

```text
(phone, normalized_name)
```

---

# 📞 Call History

The CRM allows administrators to record customer interactions and maintain a history of calls.

Call records can be associated with individual customers to provide a centralized interaction history.

---

# 🔔 Persistent Follow-Up System

The follow-up engine allows administrators to schedule future customer callbacks.

Supported workflow views include:

```text
Today
Upcoming
Overdue
```

The system prevents duplicate callbacks for the same customer at the same timestamp.

Past dates are rejected when scheduling new follow-ups.

---

# 📈 CRM Dashboard

The dashboard provides database-level aggregations for CRM statistics.

Instead of loading large datasets into application memory, counts are calculated directly at the database layer.

This helps the application remain efficient as the number of customer records increases.

---

# 🔐 Authentication & Security

The CRM is designed as an admin-only system.

Security features include:

* Admin authentication
* HMAC-signed authentication tokens
* 12-hour session expiration
* Constant-time secret comparison
* Secure temporary file handling
* Restricted CORS configuration
* Production environment variables
* Database-backed application data

Sensitive credentials are not stored directly in the source code.

---

# 🏗️ Architecture

The application follows a modern full-stack architecture.

```text
                    CRM Follow-Up System
                             │
             ┌───────────────┴───────────────┐
             │                               │
        React Frontend                  FastAPI Backend
             │                               │
             │                         Python / API
             │                               │
             └───────────────┬───────────────┘
                             │
                             ▼
                         MongoDB
                        Database
```

---

# 🛠️ Tech Stack

## Backend

* Python 3.11+
* FastAPI
* Pydantic
* Uvicorn
* Python database driver / ORM layer as configured by the project

## Frontend

* React 18
* Vite
* Lucide React
* JavaScript
* Modular component architecture

## Database

* MongoDB

MongoDB is used as the production database for storing CRM data such as:

* Customers
* Call histories
* Follow-ups
* CRM records
* Authentication-related application data

## Deployment

* Render
* Render Web Service
* Render Static Site
* Render Cron / Keepalive service

## Source Control

* GitHub

---

# ☁️ Production Deployment

The CRM system is deployed on **Render**.

The production environment consists of:

```text
Render
│
├── Backend API
│
├── React Frontend
│
└── Keepalive / Scheduled Service
         │
         ▼
      MongoDB
```

The frontend and backend are deployed as separate services.

---

# 🌐 Production Architecture

```text
                         User
                           │
                           ▼
                  React Web Application
                    Render Static Site
                           │
                           │ API Requests
                           ▼
                    FastAPI Backend
                    Render Web Service
                           │
                           │
                           ▼
                        MongoDB
                       Production DB
```

---

# 📦 Project Structure

```text
CRM-Follow-Up-System/
│
├── backend/
│   ├── app/
│   │   ├── ...
│   │   └── ...
│   │
│   ├── requirements.txt
│   └── ...
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── ...
│   │
│   ├── package.json
│   └── ...
│
├── render.yaml
├── README.md
└── ...
```

The exact internal module structure may vary depending on the current repository implementation.

---

# ⚙️ Environment Variables

Production configuration is handled through environment variables rather than hard-coded credentials.

## Backend — Render Web Service

| Variable             | Required | Description                                  |
| -------------------- | -------- | -------------------------------------------- |
| `DATABASE_URL`       | Yes      | MongoDB connection URI                       |
| `CRM_ADMIN_USERNAME` | Yes      | Admin login username                         |
| `CRM_ADMIN_PASSWORD` | Yes      | Admin login password                         |
| `CRM_AUTH_SECRET`    | Yes      | Secret used for authentication token signing |
| `CORS_ORIGINS`       | Yes      | Allowed frontend origins                     |
| `IMPORT_BATCH_SIZE`  | No       | Number of records processed per batch        |
| `MAX_UPLOAD_BYTES`   | No       | Maximum upload size                          |
| `MAX_WORKSHEET_ROWS` | No       | Maximum spreadsheet rows                     |

> The actual variable names should match the configuration used in the deployed repository.

---

# 🎨 Frontend Configuration

The React/Vite frontend requires the backend API URL.

Example:

```text
VITE_API_URL=https://your-backend-service.onrender.com
```

This allows the frontend to communicate with the FastAPI production API.

---

# 🔄 CRM Workflow

The typical workflow is:

```text
1. Admin logs in
          ↓
2. Opens CRM dashboard
          ↓
3. Imports customer spreadsheet
          ↓
4. System validates customer data
          ↓
5. Duplicate records are detected
          ↓
6. Customers are stored in MongoDB
          ↓
7. Admin opens customer record
          ↓
8. Call information is recorded
          ↓
9. Follow-up is scheduled
          ↓
10. Follow-up appears under:
       ├── Today
       ├── Upcoming
       └── Overdue
```

---

# 📥 Spreadsheet Import

The CRM is designed to process large Excel/CSV files efficiently.

The import process includes:

```text
Upload
  ↓
Validation
  ↓
Preview
  ↓
Duplicate Detection
  ↓
Batch Processing
  ↓
MongoDB
  ↓
Import Complete
```

The application uses batch processing rather than attempting to load an entire large spreadsheet into memory at once.

---

# 🧹 Data Deduplication

Duplicate customer records are identified using customer-specific identifiers.

Primary identification:

```text
consumer_number
```

Fallback identification:

```text
phone + normalized_name
```

This helps prevent duplicate customer records during repeated imports.

---

# 🔔 Follow-Up Engine

The follow-up system supports persistent scheduling.

Administrators can create follow-ups for customers and organize them into:

### Today

Follow-ups scheduled for the current date.

### Upcoming

Future scheduled follow-ups.

### Overdue

Follow-ups whose scheduled time has already passed and require attention.

The system also prevents duplicate callbacks for the same customer at identical timestamps.

---

# 📊 Dashboard Performance

Dashboard statistics are calculated at the database level where possible.

For example:

```text
Total Customers
Today's Follow-Ups
Upcoming Follow-Ups
Overdue Follow-Ups
Call Statistics
```

This avoids unnecessary loading and counting of large datasets inside application memory.

---

# 🩺 Health Checks

The backend exposes health-check endpoints for production monitoring.

### Basic Health Check

```http
GET /health
```

Used to verify that the API service is running.

### Database Readiness

```http
GET /health/ready
```

Used to verify that the application can communicate with the production database.

---

# 🖥️ Local Development

## Backend

Navigate to the backend directory:

```powershell
cd backend
```

Configure local environment variables.

Example:

```powershell
$env:DATABASE_URL='mongodb://localhost:27017/crm_follow_up'
$env:CRM_ADMIN_USERNAME='admin'
$env:CRM_ADMIN_PASSWORD='test-password'
$env:CRM_AUTH_SECRET='test-secret'
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start the backend:

```powershell
uvicorn app.main:app --reload
```

The API will normally be available at:

```text
http://127.0.0.1:8000
```

---

# 🎨 Frontend Development

Navigate to the frontend:

```powershell
cd frontend
```

Install dependencies:

```powershell
npm ci
```

Start the development server:

```powershell
npm run dev
```

Build the production frontend:

```powershell
npm run build
```

---

# 🧪 Testing

Backend tests can be executed using:

```powershell
pytest -v
```

Before deployment, verify:

* Authentication
* Customer import
* Duplicate detection
* Customer search
* Call history
* Follow-up scheduling
* Today follow-ups
* Upcoming follow-ups
* Overdue follow-ups
* API health
* Database readiness
* Frontend API connectivity

---

# 🚀 Render Deployment

The project includes:

```text
render.yaml
```

which can be used to configure the Render deployment.

The production setup contains:

```text
Render
│
├── Web Service
│     └── FastAPI Backend
│
├── Static Site
│     └── React Frontend
│
└── Cron / Keepalive
      └── Backend availability check
```

---

# 🔧 Render Backend

The backend is deployed as a Render Web Service.

Typical configuration:

### Runtime

```text
Python
```

### Build

```bash
pip install -r requirements.txt
```

### Start

```bash
uvicorn <backend-entrypoint>:app --host 0.0.0.0 --port $PORT
```

The exact entrypoint should match the backend application structure in the repository.

---

# 🎨 Render Frontend

The React/Vite application is deployed separately as a Render Static Site.

Typical workflow:

```text
GitHub
   ↓
Render
   ↓
npm install
   ↓
npm run build
   ↓
Static Frontend
```

The frontend uses:

```text
VITE_API_URL
```

to communicate with the production FastAPI backend.

---

# ⏱️ Keepalive Service

A Render scheduled service can be used to periodically call the backend health endpoint.

Example:

```text
GET /health
```

This can help reduce cold-start delays on suitable Render configurations.

The keepalive configuration is managed through:

```text
render.yaml
```

---

# 🗄️ MongoDB

MongoDB is the production database used by the CRM.

The backend connects to MongoDB using the configured database connection string.

The database stores the CRM application's persistent information, including:

```text
Customers
Calls
Follow-Ups
CRM Records
Application Data
```

The MongoDB connection string should be stored securely as an environment variable and should never be committed to GitHub.

---

# 🔐 Security Recommendations

Production credentials should always be configured through Render environment variables.

Never commit:

```text
MongoDB connection strings
Admin passwords
Authentication secrets
API keys
Private credentials
```

to the repository.

A `.gitignore` file should include local environment and secret files such as:

```text
.env
.env.local
__pycache__/
node_modules/
```

---

# 📈 Scalability

The architecture separates the frontend, backend, and database:

```text
Frontend
   │
   ▼
API
   │
   ▼
MongoDB
```

This makes it possible to independently scale:

* Frontend delivery
* API processing
* Database capacity

The application also uses batch-oriented spreadsheet processing to reduce memory usage during large imports.

---

# 🔄 Deployment Workflow

Recommended development workflow:

```text
Developer
    │
    ▼
Local Development
    │
    ├── Backend Testing
    ├── Frontend Testing
    └── Integration Testing
    │
    ▼
GitHub
    │
    ▼
Render
    │
    ├── Backend Deployment
    ├── Frontend Deployment
    └── Keepalive Deployment
    │
    ▼
Production
    │
    ▼
MongoDB
```

---

# 📋 Production Checklist

Before deploying:

### Database

* [ ] MongoDB database created
* [ ] Production connection URI configured
* [ ] Database access verified
* [ ] Credentials stored securely

### Backend

* [ ] FastAPI application configured
* [ ] Admin credentials configured
* [ ] Authentication secret configured
* [ ] CORS configured
* [ ] Health endpoint working
* [ ] Database readiness endpoint working

### Frontend

* [ ] React application builds successfully
* [ ] `VITE_API_URL` configured
* [ ] Production API connection tested
* [ ] Login flow tested

### CRM

* [ ] Customer import tested
* [ ] CSV import tested
* [ ] Excel import tested
* [ ] Duplicate detection tested
* [ ] Call history tested
* [ ] Follow-up scheduling tested
* [ ] Today view tested
* [ ] Upcoming view tested
* [ ] Overdue view tested

### Deployment

* [ ] GitHub repository connected
* [ ] Render backend deployed
* [ ] Render frontend deployed
* [ ] Keepalive configured
* [ ] Production application tested

---

# 📊 Project Information

| Category           | Details                                 |
| ------------------ | --------------------------------------- |
| Project            | CRM Follow-Up System                    |
| Type               | Admin CRM / Customer Follow-Up Platform |
| Backend            | FastAPI                                 |
| Backend Language   | Python                                  |
| Frontend           | React 18                                |
| Build Tool         | Vite                                    |
| UI Icons           | Lucide React                            |
| Database           | MongoDB                                 |
| Source Control     | GitHub                                  |
| Backend Hosting    | Render                                  |
| Frontend Hosting   | Render                                  |
| Scheduled Service  | Render                                  |
| Architecture       | Full Stack                              |
| Authentication     | Admin-only                              |
| API Health         | `/health`                               |
| Database Readiness | `/health/ready`                         |

---

# 🎯 Future Enhancements

Possible future improvements include:

* Role-based access control
* Multiple sales users
* Team management
* Advanced customer segmentation
* WhatsApp integration
* Email integration
* Automated reminders
* SMS notifications
* CRM analytics
* Sales performance dashboards
* Lead scoring
* Customer lifecycle tracking
* Export reports
* Activity timeline
* Bulk follow-up scheduling
* Advanced search and filters
* Audit logs
* Multi-tenant CRM support

---

# 👨‍💻 Project

**CRM Follow-Up System**

A full-stack CRM platform for managing customers, calls, and persistent follow-ups through a centralized admin dashboard.

Built with:

```text
React + Vite
       │
       ▼
FastAPI
       │
       ▼
MongoDB
       │
       ▼
Render
```

---

# 📄 License

Add the appropriate project license here if the repository is intended to be publicly distributed.
