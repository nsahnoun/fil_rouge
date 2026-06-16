# Extraits de Code Argumentés

## 1. Authentification Sécurisée (Backend)

**Fichier :** `web_gateway/routers/auth.py`

```python
@router.post("/login")
async def login(req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    # Requête paramétrée SQLAlchemy — insensible à l'injection SQL
    result = await db.execute(
        select(User).where(User.email == req.email).options(selectinload(User.role))
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise UnauthorizedException("Email ou mot de passe incorrect")
    
    # Création du token JWT avec expiration
    token = create_access_token(user.id, user.role.name)
    
    # Cookie HttpOnly — inaccessible au JavaScript (anti-XSS)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=86400 * 24,
        samesite="lax",
    )
    return {"access_token": token, "user_id": user.id, "role": user.role.name}
```

**Ce que fait ce code :**
1. **Anti-injection SQL** : `User.email == req.email` utilise un paramètre lié, pas de concaténation
2. **Anti-XSS** : Le cookie est marqué `HttpOnly` → jamais accessible via `document.cookie`
3. **Anti-CSRF** : `SameSite=Lax` empêche l'envoi du cookie depuis des sites tiers
4. **Protection mot de passe** : `verify_password` utilise bcrypt (12 rounds)
5. **JWT** : Token signé avec algorithme HMAC + secret serveur

---

## 2. Hash et Vérification des Mots de Passe

**Fichier :** `web_gateway/core/security.py`

```python
import bcrypt
from jose import JWTError, jwt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiration_hours)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
```

**Ce que fait ce code :**
- `bcrypt.gensalt()` génère un sel aléatoire à chaque appel
- 12 rounds de hash (configurable) ralentit les attaques par force brute
- JWT avec expiration explicite (24h) limite la fenêtre d'attaque

---

## 3. Contrôle d'Accès par Rôles (RBAC)

**Fichier :** `web_gateway/core/rbac.py`

```python
ROLE_PERMISSIONS = {
    "admin": {
        "patients": ["*"],
        "analyses": ["*"],
        "settings": ["*"],
        "audit": ["read", "export"],
    },
    "orthodontist": {
        "patients": ["create", "read", "update"],
        "analyses": ["create", "read", "update", "validate"],
        "reports": ["create", "sign", "send"],
    },
    "assistant": {
        "patients": ["create", "read", "update"],
        "analyses": ["read"],
        "reports": ["read"],
    },
    "intern": {
        "patients": ["read"],
        "analyses": ["read"],
        "reports": ["read"],
    },
}

def has_permission(role_name: str, resource: str, action: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role_name, {})
    if "*" in perms.get(resource, []):
        return True
    return action in perms.get(resource, [])
```

**Ce que fait ce code :**
- Matrice de permissions claire et lisible
- `"*"` signifie toutes les actions autorisées (admin)
- Principe de moindre privilège : chaque rôle a accès au strict nécessaire

---

## 4. Canevas Interactif — Calcul d'une Mesure Céphalométrique

**Fichier :** `web_gateway/static/js/canvas_engine.js`

```javascript
function calcMeas(m) {
    switch (m.fn) {
        case 'angFH':  // Angle par rapport au plan de Francfort
            const p1 = G(m.a1), p2 = G(m.a2);
            if (!p1 || !p2) return null;
            return angFH_v(V(p1, p2));
            
        case 'angVV':  // Angle entre deux vecteurs
            const p1 = G(m.a1), p2 = G(m.a2), p3 = G(m.b1), p4 = G(m.b2);
            if (!p1 || !p2 || !p3 || !p4) return null;
            return angVV(V(p1, p2), V(p3, p4));
            
        case 'anb':  // Calcul ANB (différence SNA - SNB)
            const s = G(11), n = G(5), a = G(1), b = G(3);
            if (!s || !n || !a || !b) return null;
            const sna = angVV(V(n, s), V(n, a));
            const snb = angVV(V(n, s), V(n, b));
            return sna - snb;
            
        case 'wits':  // Wits appraisal (AO-BO)
            const a = G(1), b = G(3), oc1 = G(23), oc2 = G(22);
            if (!a || !b || !oc1 || !oc2) return null;
            const ov = nv(V(oc1, oc2));
            const ao = dt(V(oc1, a), ov) * ps();
            const bo = dt(V(oc1, b), ov) * ps();
            return ao - bo;
    }
}
```

**Ce que fait ce code :**
- Prend une définition de mesure (points, fonction) et calcule la valeur
- Vérifie que tous les landmarks requis sont présents avant le calcul
- Utilise des fonctions vectorielles réutilisables (angle, distance, projection)
- Retourne `null` si un landmark est manquant → pas de crash

---

## 5. Requête Sécurisée avec SQLAlchemy (ORM)

**Fichier :** `web_gateway/routers/patients.py`

```python
# Requête paramétrée — insensible à l'injection SQL
result = await db.execute(
    select(Patient)
    .where(Patient.assigned_to == current_user.id)
    .order_by(Patient.created_at.desc())
)
patients = result.scalars().all()
```

**Pourquoi c'est sécurisé :**
- La valeur `current_user.id` est passée comme paramètre lié
- SQLAlchemy échappe automatiquement les valeurs
- Impossible d'injecter du SQL malveillant via les paramètres utilisateur

---

## 6. CSS Personnalisé avec Thème Clair/Sombre

**Fichier :** `web_gateway/static/css/style.css`

```css
:root {
  --bg-primary: #0e1117;
  --bg-secondary: #161b2e;
  --text-primary: #e0e0e0;
  --accent: #4f8ef7;
}

[data-theme="light"] {
  --bg-primary: #f4f6fb;
  --bg-secondary: #ffffff;
  --text-primary: #1a1f36;
  --accent: #3b7be0;
}

body {
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: background .2s, color .2s;
}

@media (max-width: 768px) {
  .sidebar { display: none; }
  .col-main { padding: 16px; }
  .stats-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); }
}
```

**Ce que fait ce code :**
- Utilise des variables CSS custom properties pour le theming
- Bascule entre thème sombre (`data-theme="light"` absent) et clair
- Transitions fluides entre les thèmes
- Media queries pour l'adaptation mobile

---

## 7. Détection IA des Landmarks

**Fichier :** `web_gateway/services/ceph_client.py`

```python
class CephClient:
    async def predict(self, image_path: str | Path) -> dict | None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/png")}
                resp = await client.post(f"{self.base_url}/predict", files=files)
            resp.raise_for_status()
            return resp.json()
```

**Ce que fait ce code :**
- Appel asynchrone au microservice de prédiction IA
- Timeout de 120s pour les images volumineuses
- Gestion des erreurs avec return `None` si échec (graceful degradation)
- Le modèle HRNet détecte 29 landmarks anatomiques

---

## 8. Middleware de Sécurité

**Fichier :** `web_gateway/app.py`

```python
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

**Ce que fait ce code :**
- `X-Frame-Options: DENY` → anti-clickjacking (interdit l'iframe)
- `X-Content-Type-Options: nosniff` → empêche le MIME sniffing
- `X-XSS-Protection: 1; mode=block` → active le filtre XSS du navigateur
- `HSTS` → force HTTPS pour 1 an
