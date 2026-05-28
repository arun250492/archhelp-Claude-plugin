# Sample Output — `django/django`

This shows the output of `analyze_repository` run on the Django framework repo.

---

## 1. System Architecture

```mermaid
graph TB
    title["django/django - Architecture"]
    style title fill:#f5f5f5,stroke:#ccc,color:#333

    subgraph Backend["Backend Layer"]
        API[API Server]
        BL[Business Logic]
        AUTH[Auth Service]
    end
    subgraph Data["Data Layer"]
        PostgreSQL[("PostgreSQL")]
        CACHE[(Cache)]
    end
    subgraph Infra["Infrastructure"]
        GitHub_Actions["GitHub Actions"]
    end

    API --> BL
    API --> AUTH
    BL --> PostgreSQL
    BL --> CACHE
```

---

## 2. Data Flow

```mermaid
flowchart LR
    User([User / Client])
    GW[API Gateway]
    AUTH[Auth Middleware]
    BL[Business Logic]
    DB[(Database)]
    CACHE[(Cache)]

    User -->|Request| GW
    GW --> AUTH
    AUTH -->|Validated| BL
    BL -->|Query| DB
    DB -->|Result| BL
    BL -->|Response| GW
    GW -->|JSON| User
    BL -.->|Cache read| CACHE
    CACHE -.->|Hit| BL

    subgraph Routes["API Routes"]
        admin["/admin/"]
        api_v1["/api/v1/"]
    end
    GW --> Routes
```

---

## 3. Entity-Relationship Diagram

```mermaid
erDiagram
    User {
        int id PK
        datetime created_at
    }
    Group {
        int id PK
        datetime created_at
    }
    Permission {
        int id PK
        datetime created_at
    }
    ContentType {
        int id PK
        datetime created_at
    }
    User }o--|| Group : "groups"
    User }o--|| Permission : "user_permissions"
    Permission }o--|| ContentType : "content_type"
```

---

## 4. Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant GW as API Gateway
    participant AUTH as Auth Service
    participant SVC as Backend Service
    participant DB as Database
    participant CACHE as Cache

    User->>GW: HTTP Request
    GW->>AUTH: Validate token
    AUTH-->>GW: 200 OK / 401
    GW->>SVC: Forward request
    SVC->>CACHE: Cache lookup
    alt Cache hit
        CACHE-->>SVC: Cached result
    else Cache miss
        SVC->>DB: Query / Mutation
        DB-->>SVC: Row set
        SVC->>CACHE: Store result
    end
    SVC-->>GW: Processed response
    GW-->>User: JSON response
```

---

## 5. Component Map

```mermaid
graph LR
    %% Module dependency map
    django["django"]
    tests["tests"]
    docs["docs"]
    extras["extras"]
    django --> tests
```

---

## 6. Deployment Topology

```mermaid
graph TB
    subgraph Internet["Internet"]
        USER([Client])
        CDN[CDN / Load Balancer]
    end
    subgraph App["Application Layer"]
        WEB[Web / Reverse Proxy]
        APP[App Server]
    end
    subgraph Persistence["Persistence Layer"]
        DB[(Primary DB)]
        REPLICA[(Read Replica)]
    end
    subgraph CI["CI / CD Pipeline"]
        GitHub_Actions["GitHub Actions"]
    end
    subgraph External["External Services"]
        Monitoring["Monitoring"]
    end

    USER --> CDN
    CDN --> WEB
    WEB --> APP
    APP --> DB
    DB --> REPLICA
    CACHE[(Cache)]
    APP --> CACHE
```
