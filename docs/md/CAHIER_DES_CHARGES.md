# Cahier des Charges — CephAnalysis

## 1. Expression des Besoins

### Contexte

Les orthodontistes réalisent des analyses céphalométriques à partir de radiographies de profil. Traditionnellement, cette tâche est effectuée manuellement : tracé papier, mesures au rapporteur et à la règle, report sur fiche. Ce processus est long, sujet aux erreurs et difficile à partager.

### Problématique

Les praticiens ont besoin d'un outil numérique permettant de :
1. **Automatiser** la détection des points de repère anatomiques (landmarks) via IA
2. **Visualiser** et ajuster manuellement ces points sur un canevas interactif
3. **Calculer** instantanément les mesures céphalométriques selon plusieurs méthodes d'analyse reconnues
4. **Générer** des rapports cliniques PDF
5. **Collaborer** avec une équipe via un système multi-utilisateurs avec rôles

### Utilisateurs Cibles

| Rôle | Description |
|------|-------------|
| **Administrateur** | Gère les utilisateurs, les rôles, les paramètres système |
| **Orthodontiste** | Crée et valide les analyses, génère les rapports, signe les documents |
| **Assistant(e)** | Crée les dossiers patients, importe les radiographies, suit les tâches |
| **Stagiaire/Interne** | Consulte les analyses et rapports en lecture seule |

### Fonctionnalités Attendues

| # | Fonctionnalité | Priorité |
|---|---------------|----------|
| 1 | Inscription / connexion sécurisée | Critique |
| 2 | Gestion des patients (CRUD) | Critique |
| 3 | Import de radiographies (JPEG, PNG, DICOM) | Critique |
| 4 | Détection automatique des landmarks par IA | Critique |
| 5 | Canevas interactif de modification des landmarks | Critique |
| 6 | Calcul d'analyses céphalométriques (12 méthodes) | Critique |
| 7 | Génération de rapports PDF | Haute |
| 8 | Export PNG/JSON des analyses | Haute |
| 9 | Workflow de relecture et validation | Haute |
| 10 | Tableau de bord statistique | Moyenne |
| 11 | Comparaison d'analyses | Moyenne |
| 12 | Journal d'audit | Moyenne |
| 13 | Thème clair/sombre | Basse |

### Contraintes Techniques

- Application web responsive (mobile, tablette, desktop)
- Déploiement Docker
- Base de données SQL (relationnelle)
- API REST documentée
- Authentification JWT sécurisée
- Contrôle d'accès par rôles (RBAC)
- Conformité RGPD (consentement patient, traçabilité)
- Interface en français
