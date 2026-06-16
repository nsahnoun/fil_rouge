# Spécifications Techniques

## 1. Choix Technologiques

| Couche | Technologie | Justification |
|--------|------------|---------------|
| **Framework web** | FastAPI 0.136 | Performance asynchrone, documentation OpenAPI automatique, validation Pydantic |
| **Base de données** | SQLite (dev) / PostgreSQL (prod) | SQLite pour la simplicité du MVP, migration PostgreSQL possible via SQLAlchemy |
| **ORM** | SQLAlchemy 2.0 async | Requêtes paramétrées (anti-injection SQL), migrations Alembic |
| **Auth** | JWT + bcrypt | Cookie HttpOnly pour le web, Bearer pour l'API, hash bcrypt 12 rounds |
| **Frontend** | Jinja2 + Vanilla JS | SSR pour le SEO et les performances, pas de dépendance framework JS |
| **Canvas** | HTML5 Canvas + Vanilla JS | Canevas interactif pour les landmarks, léger et performant |
| **PDF** | WeasyPrint 68.1 | Génération PDF côté serveur depuis HTML/CSS |
| **ML** | TensorFlow + HRNet | Modèle entraîné pour la détection de 29 landmarks céphalométriques |
| **Proxy** | Nginx | Reverse proxy, rate limiting, cache statique, SSL |
| **Cache** | Redis | Sessions, rate limiter |
| **Conteneurisation** | Docker + Docker Compose | 4 services : gateway, ceph_api, redis, nginx |

## 2. Architecture MVC

```
Modèles (models.py)        → 18 classes SQLAlchemy
Vues (templates/)           → 16 templates Jinja2
Contrôleurs (routers/)      → 8 routeurs FastAPI
Services (services/)        → 3 services métier
```

### Flux de données typique

```
1. Utilisateur upload une radio → POST /api/radios/upload
2. Gateway sauvegarde l'image → SQLite (radios)
3. Gateway appelle ceph_api → POST /predict (HTTP)
4. ceph_api retourne 29 landmarks (x, y) + confidences
5. Gateway stocke les landmarks → SQLite (analyses)
6. Utilisateur ajuste sur le canvas → Interface JS
7. Calcul des mesures → canvas_engine.js (12 méthodes)
8. Export PDF → WeasyPrint / jsPDF
```

## 3. Sécurité

### Protection contre les failles

| Faille | Protection | Implémentation |
|--------|-----------|----------------|
| **Injection SQL** | ORM avec requêtes paramétrées | SQLAlchemy `select(User).where(User.email == :email)` |
| **XSS** | Jinja2 auto-escape + CSP | Templates échappés par défaut |
| **CSRF** | Cookie HttpOnly + SameSite=Lax | Token JWT dans cookie non accessible en JS |
| **Mots de passe** | Bcrypt (12 rounds) | `bcrypt.hashpw(password.encode(), bcrypt.gensalt())` |
| **Rate limiting** | Nginx limit_req | 30 req/s général, 5 req/s auth |
| **Headers sécurité** | Middleware FastAPI | X-Frame-Options: DENY, HSTS, X-Content-Type-Options: nosniff |

### Exemple : Requête SQL paramétrée (anti-injection)

```python
# Routers/auth.py - Connexion
result = await db.execute(
    select(User).where(User.email == req.email).options(selectinload(User.role))
)
# req.email est passé comme paramètre, jamais concaténé dans la requête SQL
```

### RBAC (Role-Based Access Control)

```python
ROLE_PERMISSIONS = {
    "admin":        { "patients": ["*"], "analyses": ["*"], ... },
    "orthodontist": { "patients": ["create","read","update"], ... },
    "assistant":    { "patients": ["create","read","update"], "analyses": ["read"], ... },
    "intern":       { "patients": ["read"], "analyses": ["read"], ... },
}
```

## 4. Conformité RGPD

| Exigence | Implémentation |
|----------|---------------|
| Consentement patient | Table `consent_logs` avec versioning, hash, signature |
| Traçabilité | Table `audit_logs` : qui a fait quoi, quand, depuis quelle IP |
| Minimisation des données | Seules les données nécessaires sont collectées |
| Droit à l'effacement | Suppression possible des patients et données associées |
| Sécurité des données | Chiffrement (bcrypt), transport HTTPS (nginx + SSL) |
| Tenue de registre | Journal d'audit complet et horodaté |

## 5. Accessibilité

- Contraste suffisant (thème sombre/clair validé)
- Labels sur tous les champs de formulaire
- Navigation au clavier
- `aria-label` sur les boutons d'icônes
- Tailles de police relatives (rem/em)

## 6. Performance

- Async I/O partout (aiosqlite, httpx)
- Cache statique nginx (max-age 1 an pour assets)
- SSR sans waterfall CSR
- Images radiographiques en JPEG progressif

## 7. Tests

- Framework : pytest + pytest-asyncio
- Base de données : SQLite in-memory
- Couverture : 94%
- 12 fichiers de test, ~154 tests
- Testés : models, auth, users, patients, analyses, reports, admin, pages, core, radios, services
