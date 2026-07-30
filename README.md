# Smart Jira Clone: AI-Powered Enterprise Project Management Platform

A highly scalable, production-ready project management backbone designed with **Clean Architecture** and **Domain-Driven Design (DDD)** primitives. The platform decouples complex business rules into rich object-oriented domain frameworks while providing real-time data state synchronization across multi-container Docker topologies.

---

## 🚀 Key Feature Milestones (Phases 1–5 Complete)

### 🧱 Enterprise Domain Layer (DDD)
- **Object-Oriented Invariants**: Enforces structural polymorphic rules for complex tasks (`FeatureTask`, `BugTask`) utilizing strict encapsulation and standard engineering design patterns (`TaskFactory`).
- **Clean Architecture Boundaries**: Fully decoupled codebase mapping out clear separate application lines: `Domain` (Core rules), `Use Cases` (Application workflows), and `Infrastructure` (Frameworks, Drivers, Database tools).

### 🛡️ Production Security & Granular RBAC
- **JWT Authentication Flow**: Replaced insecure development tracking matrices with industry-standard cryptographic claims verification via `python-jose` and zero-trust verification signatures.
- **Role-Based Access Control**: Strict database-backed protection guards securing endpoints specifically across target organizational contexts (`Admin`, `ProjectManager`, `Developer`).
- **Cryptographic Hashing**: Fully isolated passlib credential protection utilizing salt-reinforced `Bcrypt` parsing blocks.

### 🗄️ Relational Persistence & Isolation
- **Optimized Relational Schemas**: High-performance PostgreSQL blueprint featuring multi-table relations linking Users, Projects, Tasks, tags, Comments, and Audit Activity/Logs.
- **Composite Indexing**: Database-enforced optimization graphs balancing high-frequency search lookups (e.g., project-to-status matching indices).
- **Alembic Database Migrations**: Rigorous schema changes tracked and rolled out safely via migration revision graphs instead of runtime development reflection scripts.

### 🌐 Scaled Real-Time Sync & AI Integration
- **Distributed Redis Pub/Sub**: Replaced localized in-memory connection dictionaries with an asynchronous horizontal Redis backplane, syncing real-time drag-and-drop Kanban card transformations across separate backend container instances.
- **Protected AI Agent (OpenAI SDK)**: Secure, role-guarded requirements analysis service built over the official asynchronous OpenAI Python SDK leveraging structured schema output formatting.

---

## 🛠️ The Tech Stack Core

- **Backend Framework**: FastAPI (Asynchronous Engine + Pydantic v2 data validation schemas)
- **Database Engine**: PostgreSQL + SQLAlchemy 2.0 (Async Engine execution context via `asyncpg`)
- **Caching & Broker Core**: Redis (Distributed asynchronous pub/sub frame stream routing)
- **Frontend Layer**: React 19 + TypeScript + Tailwind CSS (Native browser Drag-and-Drop)
- **Container Infrastructure**: Docker Engine + Docker Compose

---

## ⚡ Quick Start Local Infrastructure Replication

### 1. Build and Run Application Containers
Spin up the decoupled multi-container ecosystem seamlessly via Docker:
```bash
docker compose up --build -d
```

### 2. Seed Mock Workspace Databases
Inject sample organizational schemas, encrypted team users, and default project frames into PostgreSQL:
```bash
docker compose exec backend bash -c "PYTHONPATH=/backend/app python3 -m src.seed_data"
```

### 3. Run Automated Validation Test Suites
Trigger the test assertions to verify domain invariants and secure access endpoints:
```bash
docker compose exec backend bash -c "PYTHONPATH=/backend/app python3 -m pytest --disable-warnings"
```

---

## 📡 Live Operational Endpoints

Once the infrastructure completes instantiation, evaluate system frameworks across active ports:
- **Interactive OpenAPI Documentation Panel**: `http://localhost:8000/docs`
- **Hot-Reloading Frontend Development Board**: `http://localhost:5173`
- **Distributed Microservice Health Check Tracker**: `http://localhost:8000/health`
