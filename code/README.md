# NexaFi — Code Directory

Restructured source code for the NexaFi fintech platform, organized into three top-level directories.

## Directory Structure

```
code/
├── backend/                    # Flask microservices & shared infrastructure library
│   ├── shared/                 # Shared library used by ALL services
│   │   ├── audit/              # Audit logging
│   │   ├── config/             # Infrastructure configuration
│   │   ├── database/           # Database manager (SQLite + migrations)
│   │   ├── middleware/         # Auth & rate-limiter middleware
│   │   ├── nexafi_logging/     # Structured logging
│   │   ├── utils/              # Circuit breaker, cache, message queue
│   │   ├── validation_schemas/ # Marshmallow schemas & validators
│   │   ├── security.py         # Core security (MFA, encryption, fraud detection)
│   │   └── open_banking_compliance.py  # PSD2 / FAPI 2.0 compliance
│   ├── api-gateway/            # Central API gateway & routing (port 5000)
│   ├── auth-service/           # OAuth 2.0 / OIDC authentication (port 5011)
│   ├── compliance-service/     # AML, KYC, sanctions screening (port 5005)
│   ├── credit-service/         # Credit scoring & loan management (port 5008)
│   ├── document-service/       # Document storage & templates (port 5006)
│   ├── ledger-service/         # Double-entry accounting & journals (port 5002)
│   ├── notification-service/   # Email, SMS, in-app notifications (port 5006)
│   ├── open-banking-gateway/   # PSD2 open banking API gateway (port 5010)
│   ├── payment-service/        # Payments, wallets, transactions (port 5003)
│   ├── user-service/           # User auth, registration, RBAC (port 5001)
│   ├── infrastructure/         # Docker Compose, Redis config, startup scripts
│   └── tests/                  # Backend test suite (7 files)
│
├── ml_services/                # AI & machine learning services
│   ├── ai-service/             # AI predictions, cash flow forecasting (port 5004)
│   ├── analytics-service/      # Dashboards, metrics, reports (port 5009)
│   ├── ai-explainability/      # Explainable AI engine (SHAP, LIME, regulatory)
│   │   └── model-interpretation/
│   └── tests/                  # ML services test suite
│
└── platform_services/          # Infrastructure, security engines & enterprise integrations
    ├── security/               # Advanced security engines
    │   ├── threat-detection/   # Real-time anomaly & threat detection
    │   └── zero-trust/         # Zero-trust architecture & risk scoring
    ├── scalability/            # High-performance infrastructure modules
    │   ├── caching/            # Multi-tier cache (Redis, Memcache, in-memory)
    │   └── distributed-computing/  # Distributed transaction processing (Kafka, RabbitMQ)
    ├── enterprise-integrations/ # ERP / enterprise system connectors
    │   ├── oracle/             # Oracle ERP Cloud integration
    │   ├── sap/                # SAP ERP / S4HANA integration
    │   └── shared/             # Base integration framework & manager
    └── tests/                  # Platform services test suite
```

## Import Architecture

All services resolve `backend/shared/` via runtime `sys.path` injection:

**Backend services** (`backend/<service>/src/main.py`):

```python
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
```

**ML services** (`ml_services/<service>/src/main.py`):

```python
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "..", "backend", "shared"))
```

**Platform services** (`platform_services/enterprise-integrations/shared/base_integration.py`):

```python
sys.path.insert(0, os.path.join(_BASE_DIR, '..', '..', '..', 'backend', 'shared'))
```

## Running Tests

```bash
# Backend tests
cd backend && python -m pytest tests/ -v

# ML services tests
cd ml_services && python -m pytest tests/ -v

# Platform services tests
cd platform_services && python -m pytest tests/ -v
```

## Service Ports

| Service              | Port |
| -------------------- | ---- |
| API Gateway          | 5000 |
| User Service         | 5001 |
| Ledger Service       | 5002 |
| Payment Service      | 5003 |
| AI Service           | 5004 |
| Compliance Service   | 5005 |
| Document Service     | 5006 |
| Analytics Service    | 5009 |
| Auth Service         | 5011 |
| Open Banking Gateway | 5010 |
