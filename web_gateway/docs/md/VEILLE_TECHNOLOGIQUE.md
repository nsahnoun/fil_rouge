# Veille Technologique

## 1. Comparaison des Frameworks de Data Dashboarding

### Contexte

Pour une application d'analyse céphalométrique, nous avons évalué plusieurs frameworks. Le choix initial s'est porté sur Streamlit, puis nous avons migré vers FastAPI.

### Streamlit vs Dash vs FastAPI

| Critère | Streamlit | Dash (Plotly) | FastAPI + Jinja2 |
|---------|-----------|---------------|------------------|
| **Courbe d'apprentissage** | Très faible | Modérée | Modérée |
| **Rapidité de prototypage** | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| **Performance** | ★★☆☆☆ (rerun complet) | ★★★☆☆ | ★★★★★ (async) |
| **API REST** | ❌ | ✅ | ✅ (natif) |
| **Authentification** | ❌ (pas natif) | ❌ (pas natif) | ✅ (JWT, OAuth2) |
| **RBAC** | ❌ | ❌ | ✅ |
| **Multi-pages** | ❌ (monopage) | ✅ | ✅ |
| **Templates HTML** | ❌ (composants internes) | ❌ | ✅ (Jinja2) |
| **Tests** | ❌ (difficile) | ★★☆☆☆ | ★★★★★ (pytest) |
| **Contrôle du HTML/CSS** | ★★☆☆☆ | ★★★☆☆ | ★★★★★ |
| **Canvas interactif** | ★★☆☆☆ (rerun lent) | ★★★☆☆ | ★★★★★ (JS pur) |
| **Base de données** | ★★☆☆☆ | ★★★☆☆ | ★★★★★ (SQLAlchemy) |
| **Documentation API** | ❌ | ❌ | ✅ (OpenAPI/Swagger) |
| **Déploiement** | Docker simple | Docker simple | Docker + nginx |
| **Idéal pour** | Prototypes, data viz | Dashboards analytiques | Applications pro complètes |

### Conclusion

**Streamlit** est idéal pour le prototypage rapide et les démonstrations (nous avons commencé avec une v5 fonctionnelle en 2 semaines). **FastAPI** est le choix professionnel pour une application clinique nécessitant sécurité, performance, tests et maintenabilité.

---

## 2. Numba : Accélération Python pour le Calcul Vectoriel

### Contexte

Le calcul des 29 landmarks à partir de l'image radiographique nécessite des opérations vectorielles intensives.

### Solution : Numba (JIT Compilation)

Numba est un compilateur JIT (Just-In-Time) pour Python qui permet d'accélérer les boucles numériques :

```python
from numba import jit
import numpy as np

@jit(nopython=True)
def compute_heatmap(heatmap, coords):
    """Accélération du post-processing des heatmaps HRNet"""
    for i in range(coords.shape[0]):
        y, x = np.unravel_index(np.argmax(heatmap[i]), heatmap[i].shape)
        coords[i, 0] = x
        coords[i, 1] = y
    return coords
```

Avantages :
- Jusqu'à 100× plus rapide que du Python pur
- Pas de modification majeure du code
- Compatible avec NumPy et TensorFlow

---

## 3. HRNet pour la Détection de Points Anatomiques

### Contexte

La détection de landmarks sur des radiographies est un problème de « human pose estimation » adapté à la céphalométrie.

### Pourquoi HRNet ?

| Réseau | Précision | Taille | Inférence |
|--------|-----------|--------|-----------|
| ResNet | ★★★☆☆ | Moyenne | Rapide |
| U-Net | ★★★★☆ | Grande | Lente |
| **HRNet** | **★★★★★** | Grande | **Rapide** |
| ViT (Vision Transformer) | ★★★★☆ | Très grande | Lente |

**HRNet** maintient des représentations haute résolution tout au long du réseau, contrairement aux architectures classiques qui réduisent progressivement la résolution. Cela le rend particulièrement adapté à la localisation précise de points anatomiques.

### Références

- Wang et al., "Deep High-Resolution Representation Learning for Visual Recognition" (TPAMI 2020)
- Applications : détection de joints humains, landmarks faciaux, landmarks céphalométriques

---

## 4. FastAPI vs Flask vs Django

### Contexte

Pour le framework web backend, trois options principales en Python :

| Critère | Flask | Django | FastAPI |
|---------|-------|--------|---------|
| **Async natif** | ❌ (extension) | ❌ (partiel) | ✅ (starlette) |
| **Validation** | ❌ (manuel) | ❌ (manuel) | ✅ (Pydantic) |
| **OpenAPI** | ❌ (flasgger) | ❌ (drf-yasg) | ✅ (automatique) |
| **Performance** | ★★★☆☆ | ★★☆☆☆ | ★★★★★ |
| **ORM** | ❌ (SQLAlchemy) | ✅ (Django ORM) | ❌ (SQLAlchemy) |
| **Admin** | ❌ | ✅ (django-admin) | ❌ |
| **Templates** | ✅ (Jinja2) | ✅ (Django templates) | ✅ (Jinja2) |
| **Écosystème** | Modéré | Très large | Croissant |

**Choix : FastAPI** pour sa performance asynchrone, sa validation automatique, sa documentation OpenAPI intégrée, et sa flexibilité.

---

## 5. WeasyPrint vs Puppeteer vs ReportLab pour la Génération PDF

| Critère | WeasyPrint | Puppeteer | ReportLab |
|---------|-----------|-----------|-----------|
| **Format source** | HTML + CSS | HTML + JS | Python natif |
| **Courbe apprentissage** | Faible | Modérée | Élevée |
| **Qualité rendu** | ★★★★☆ | ★★★★★ | ★★★☆☆ |
| **CSS moderne** | ★★★☆☆ | ★★★★★ | ❌ |
| **Déploiement** | Simple (pip) | Complexe (Chrome) | Simple (pip) |
| **Performance** | ★★★★☆ | ★★★☆☆ | ★★★★★ |

**Choix : WeasyPrint** pour sa simplicité (HTML vers PDF sans navigateur), sa bonne qualité de rendu, et son déploiement léger.

---

## 6. SQLite vs PostgreSQL

| Critère | SQLite | PostgreSQL |
|---------|--------|------------|
| **Déploiement** | Aucun (fichier) | Serveur dédié |
| **Performance** | ★★★☆☆ (mono-lecteur) | ★★★★★ (multi-lecteurs) |
| **Fonctionnalités** | Basiques | Avancées (JSON, GIS, ...) |
| **Sauvegarde** | Copie fichier | pg_dump |
| **Concurrence** | Limité (write lock) | Excellente |

**Choix pour le MVP : SQLite** (zéro configuration, fichier unique). Migration vers PostgreSQL prévue pour la production multi-utilisateurs.

---

## Sources

- [Data Dashboarding: Streamlit vs Dash vs Shiny vs Voila](https://www.datarevenue.com/en-blog/data-dashboarding-streamlit-vs-dash-vs-shiny-vs-voila)
- [Numba: Accelerating Pure Python Code](https://ipython-books.github.io/52-accelerating-pure-python-code-with-numba-and-just-in-time-compilation/)
- [HRNet: Deep High-Resolution Representation Learning](https://github.com/HRNet/HRNet-Image-Classification)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [WeasyPrint Documentation](https://doc.courtbouillon.org/weasyprint/stable/)
