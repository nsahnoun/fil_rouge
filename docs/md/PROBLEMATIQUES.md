# Problématiques Rencontrées et Solutions

## 1. Migration Streamlit → FastAPI

### Problème

L'application a d'abord été développée en Streamlit (`ceph_app.py`, v5). Streamlit est excellent pour le prototypage rapide, mais présentait plusieurs limitations pour une application clinique professionnelle :

- **Architecture monolithique** : tout le code dans un seul fichier de 1769 lignes
- **Pas de routing** : impossible d'avoir des URLs propres
- **Pas de contrôle d'accès** : Streamlit ne gère pas les rôles utilisateurs
- **Performances** : rerun complet à chaque interaction
- **Multi-utilisateurs** : pas de gestion de sessions
- **API** : pas de REST API pour l'intégration avec d'autres systèmes

### Solution

Refonte complète en **FastAPI** avec architecture MVC :

```
Streamlit (monolithique)       FastAPI (MVC)
─────────────────────          ─────────────────
ceph_app.py (1769 lignes)      web_gateway/
  ├── UI tout en un              ├── routers/     (8 contrôleurs)
  ├── logique métier             ├── services/    (3 services)
  ├── base de données            ├── models.py    (18 modèles)
  └── pas de tests               ├── templates/   (16 templates)
                                 ├── static/      (JS + CSS)
                                 └── tests/       (154 tests)
```

### Résultat

- Architecture propre et maintenable (SOLID)
- API REST documentée (Swagger `/docs`)
- Authentification JWT sécurisée
- RBAC avec 4 rôles
- 94% de couverture de tests
- Déploiement Docker

---

## 2. Canevas Interactif : Streamlit → JavaScript Pur

### Problème

Le canevas de manipulation des landmarks était écrit en Python/Streamlit avec des `st.image` et `st.slider`. Cela rendait l'interaction lente (rerun Streamlit à chaque modification) et limitait les possibilités (pas de drag-and-drop fluide, pas de zoom/pan performant).

### Solution

Réécriture complète du canevas en **Vanilla JavaScript** (`canvas_engine.js`) :

```javascript
// canvas_engine.js — 721 lignes
// Fonctionnalités :
// - Canvas HTML5 avec rendu fluide
// - Drag-and-drop des 29 landmarks
// - Zoom (molette) et pan (clic droit)
// - Tracés anatomiques (splines, tooth SVGs)
// - 14 plans de référence
// - 12 méthodes d'analyse avec calcul temps réel
// - Export PNG, JSON, PDF (jsPDF)
// - Support tactile (mobile/tablette)
```

### Résultat

- Interactions fluides et temps réel
- Pas de rechargement serveur
- Compatible mobile (touch events)
- Export PDF côté client avec jsPDF
- Code maintenable et modulaire

---

## 3. Détection des Landmarks par IA

### Problème

La détection manuelle des 29 points anatomiques sur une radiographie prend 5 à 10 minutes pour un orthodontiste expérimenté. La précision varie selon l'opérateur.

### Solution

Entraînement d'un modèle **HRNet** (High-Resolution Network) sur un dataset de radiographies céphalométriques annotées :

```
Modèle : HRNet-W64
Input  : 800×800 pixels
Output : 29 landmarks (x, y) + scores de confiance
Format : TensorFlow .keras
```

L'API de prédiction est un microservice séparé (`ceph_api.py`) qui communique avec la gateway via HTTP :

```
Gateway ──POST /predict (image)──▶ ceph_api ──TensorFlow──▶ landmarks JSON
```

### Résultat

- Détection automatique en ~2 secondes
- L'orthodontiste peut ensuite ajuster manuellement les points
- Workflow : IA → ajustement manuel → validation

---

## 4. Gestion de la Calibration

### Problème

Les mesures céphalométriques doivent être en millimètres réels, mais les radiographies numériques n'ont pas de métadonnées de pixel spacing fiables.

### Solution

Outil de calibration intégré au canevas :

1. L'utilisateur clique sur deux points d'une règle présente sur l'image
2. Il saisit la distance réelle en mm
3. Le `pixelSpacing` est calculé : `mm / pixels`
4. Toutes les mesures sont automatiquement converties

```javascript
function startCalib() { calibState = 'pt1'; /* mode calibration */ }

// Conversion pixels → mm
const ps = () => pixelSpacing;

function dist(p1, p2) {
    return mg(V(p1, p2)) * ps();  // distance en mm
}
```

---

## 5. Délai d'Inférence et Expérience Utilisateur

### Problème

La prédiction IA prend 2-3 secondes, pendant lesquelles l'utilisateur ne doit pas bloquer sur un écran vide.

### Solution

- Indicateur de chargement visuel sur le canevas
- Appel API asynchrone (non-bloquant)
- Timeout géré (120s maximum)
- Affichage progressif : dès que la prédiction revient, les landmarks apparaissent immédiatement

---

## 6. Génération de Rapports PDF

### Problème

Les rapports cliniques doivent contenir :
- L'image radiographique avec les tracés
- Le tableau des mesures
- Les valeurs de référence et écarts
- L'évaluation clinique

### Solution

Deux méthodes de génération PDF :

1. **PDF côté serveur** (WeasyPrint) : pour les rapports complets
   ```python
   # report_service.py
   template = env.get_template("clinical_report.html")
   html = template.render(patient=patient, analysis=analysis, ...)
   pdf = weasyprint.HTML(string=html).write_pdf()
   ```

2. **PDF côté client** (jsPDF) : pour l'export rapide depuis le canevas
   ```javascript
   // canvas_engine.js
   const doc = new jspdf.jsPDF('landscape', 'mm', 'a4');
   doc.addImage(canvas.toDataURL('image/jpeg', 0.88), 'JPEG', ...);
   // ... table des mesures
   doc.save(`ceph_${analysis}.pdf`);
   ```
