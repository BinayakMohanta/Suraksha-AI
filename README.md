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


