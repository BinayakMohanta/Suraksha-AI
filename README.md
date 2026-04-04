# Secure Gig Guardian

A comprehensive platform providing gig workers with essential tools for financial protection, risk management, and insurance coverage. Secure Gig Guardian empowers independent contractors with real-time insights and policy management.

## Features

- **Dynamic Pricing Engine**: AI-powered pricing optimization based on market conditions and risk factors
- **Risk Pulse Dashboard**: Real-time monitoring of key performance metrics and risk assessments
- **Micro Ledger**: Detailed transaction tracking and financial records
- **Policy Management**: Easy policy creation, viewing, and management
- **Telemetry Insights**: Comprehensive analytics and performance tracking
- **Payout Banner**: Transparent payout information and scheduling
- **Status Header**: Real-time status updates and alerts
- **Responsive UI**: Modern, accessible interface built with shadcn/ui

## Tech Stack

### Frontend
- **React** 18+ with TypeScript
- **Vite** - Fast build tooling
- **Tailwind CSS** - Utility-first styling
- **shadcn/ui** - High-quality React components
- **Tanstack Query** - Server state management
- **Framer Motion** - Smooth animations
- **React Router** - Client-side routing

### Backend
- **FastAPI** - Modern Python web framework
- **Uvicorn** - ASGI server
- **scikit-learn** - Machine learning for pricing optimization
- **Joblib** - Model serialization

## Installation

### Prerequisites
- Node.js 18+
- Python 3.8+
- npm or bun package manager

### Frontend Setup

```bash
# Clone the repository
git clone https://github.com/ArjunJayakrishnan-codes/secure-gig-guardian.git
cd secure-gig-guardian

# Install dependencies
npm install
# or
bun install
```

### Backend Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration/Environment Setup

### Frontend Configuration

Create a `.env` file in the root directory (if needed):

```env
VITE_API_URL=http://localhost:8000
```

### Backend Configuration

The FastAPI server runs on `http://localhost:8000` by default.

Environment variables for backend can be set in the terminal or a `.env` file.

### Authentication Configuration

Sign-in is handled via Supabase Auth. Configure frontend environment variables:

```env
VITE_SUPABASE_URL=https://<your-project-ref>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<your-anon-publishable-key>
SUPABASE_URL=https://<your-project-ref>.supabase.co
SUPABASE_ANON_KEY=<your-anon-publishable-key>
```

For Docker deployments on Render, runtime environment variables are enough: the frontend now bootstraps Supabase config from `/api/public-config` if Vite `VITE_*` vars were not present at build time.

- Users sign in/sign up from the `/auth` page.
- Protected pages are guarded client-side by Supabase session state (`AuthProvider` + `ProtectedRoute`).
- Policy API ownership checks are enforced server-side using the Supabase bearer token and user identity.

### Deploying to Render

This repo includes a `Dockerfile` that builds the frontend and runs the FastAPI backend. To deploy on Render you can use the provided `render.yaml` manifest which will build the Docker image and run the service.

Steps:

1. Push your repository to GitHub/GitLab.
2. In Render, create a new service and select "Infrastructure as Code" and connect your repo — Render will use `render.yaml`.
3. Set the environment variables in the Render dashboard (Environment → Environment Variables):

	- `MONGODB_URI` — e.g. `mongodb://username:password@host:27017` (leave blank to use the in-memory fallback)
	- `MONGODB_DB` — `secure_gig_guardian`
	- `MONGODB_COLLECTION` — `insurance_policies`
	- `MONGODB_CLAIMS_COLLECTION` — `claims`

4. Optionally set `PORT` (the Docker container respects the `PORT` env var). Render sets this automatically.

Notes:

- If `MONGODB_URI` is not set or the database is unreachable, the app falls back to an in-memory policy store (data will not persist across restarts). Set `MONGODB_URI` to enable persistence.
- Claims use the same MongoDB connection and can be configured with `MONGODB_CLAIMS_COLLECTION`.
- The Dockerfile already builds the frontend into `/app/dist` and the backend serves that folder when present.
 - The Dockerfile already builds the frontend into `/app/dist` and the backend serves that folder when present.

Seeding the database
--------------------

You can seed example policies into a MongoDB instance using the provided script. Set `MONGODB_URI` (and optionally `MONGODB_DB`/`MONGODB_COLLECTION`) and run:

```bash
MONGODB_URI="mongodb+srv://<user>:<pass>@cluster0.abcd.mongodb.net" python scripts/seed_policies.py
```

This inserts three sample policies (`POL-001`, `POL-002`, `POL-003`) and will skip duplicates.


## Quick Start Guide

### Start Development Servers

```bash
# Terminal 1 - Frontend (Vite dev server)
npm run dev
# Runs at http://localhost:5173

# Terminal 2 - Backend (FastAPI)
python api_server.py
# Runs at http://localhost:8000
```

### Build for Production

```bash
# Frontend build
npm run build

# Start preview server
npm run preview
```

### Run Tests

```bash
# Run tests once
npm run test

# Watch mode
npm run test:watch
```

### Linting

```bash
npm run lint
```

## Project Structure

```
secure-gig-guardian/
├── src/
│   ├── components/          # React components
│   ├── pages/               # Page components
│   ├── hooks/               # Custom React hooks
│   ├── lib/                 # Utility functions
│   ├── App.tsx              # Main app component
│   └── main.tsx             # Entry point
├── public/                  # Static assets
├── api_server.py            # FastAPI backend
├── dynamic_pricing.py       # Pricing algorithm
├── model.joblib             # ML model
├── requirements.txt         # Python dependencies
└── package.json             # Node dependencies
```


