# Maquettage de l'Application OrthoAnalyse

## Architecture de navigation

![Sitemap](maquettes/00_sitemap.svg)

L'application suit une architecture hiérarchique à 3 niveaux :
1. **Authentification** → page de connexion
2. **Tableau de bord** → hub central avec statistiques et accès rapides
3. **Modules fonctionnels** → Patients, Analyses, Rapports, Administration

---

## Zoning — Structure globale

![Zoning](maquettes/10_zoning.svg)

Toutes les pages connectées partagent une structure commune :

| Zone | Rôle |
|---|---|
| **Sidebar** (220px) | Navigation principale, logo, rôle utilisateur |
| **Header** (55px) | Titre de page, profil, sélecteur de langue |
| **Contenu principal** | Zone dynamique selon la page |
| **Zone d'action** | Boutons, pagination, statut |

---

## Écrans

### 1. Connexion

![Login](maquettes/01_login.svg)

Page d'authentification centrée avec :
- Logo et titre de l'application
- Champ email / mot de passe
- Bouton de connexion
- Lien "Mot de passe oublié"
- Pied de page avec version et copyright

---

### 2. Tableau de bord

![Dashboard](maquettes/02_dashboard.svg)

Vue d'ensemble avec :
- **4 cartes statistiques** : Patients, Analyses, Rapports, En attente
- **Tableau des patients récents** : nom, email, téléphone, dernière visite
- **Actions rapides** : nouveau patient, nouvelle analyse, nouveau rapport

---

### 3. Liste des patients

![Patients](maquettes/03_patients_list.svg)

Gestion des patients avec :
- **Barre de recherche** avec champ texte
- **Filtres** par statut : Tous, Actifs, En traitement, Terminés, Consultation
- **Tableau complet** : nom, âge, sexe, téléphone, dernière analyse, statut
- **Pagination** pour naviguer entre les pages

---

### 4. Détail patient — Timeline

![Patient Detail](maquettes/04_patient_detail.svg)

Fiche patient avec :
- **Carte d'identité** : photo/avatar, nom, âge, sexe, téléphone, numéro de dossier
- **Timeline chronologique** : historiques des événements (visites, radios, analyses, rapports)
- Chaque événement affiche : date, titre, description, icône de type

---

### 5. Canvas d'analyse céphalométrique

![Canvas](maquettes/05_canvas_analysis.svg)

Écran principal d'analyse avec :
- **Barre d'outils** : dessiner, placer des points, mesurer, annuler, réinitialiser
- **Zone d'image** : affichage de la téléradiographie avec les 32 landmarks détectés
- **Panneau latéral des mesures** : liste des mesures avec valeur et norme
- **Barre de statut** : informations patient, état de validation
- **Bouton de validation** pour finaliser l'analyse

---

### 6. Résultats d'analyse

![Résultats](maquettes/06_analysis_results.svg)

Affichage détaillé des résultats :
- **Tableau des mesures** : mesure, valeur, norme, statut (✓/⚠)
- **Résumé diagnostique** : classification, divergence, incisives, profil
- **Actions** : générer le rapport, comparer avec analyses précédentes

---

### 7. Rapport d'analyse

![Rapport](maquettes/07_report.svg)

Rapport généré automatiquement :
- **En-tête** : logo cabinet, informations patient, date
- **Tableau des mesures** principales avec commentaires cliniques
- **Conclusion** : résumé diagnostique et évolution
- **Signature numérique** du praticien
- **Bouton d'export** PDF

---

### 8. Administration — Utilisateurs

![Admin Users](maquettes/08_admin_users.svg)

Gestion des comptes :
- **Barre de recherche** et bouton d'ajout
- **Tableau des utilisateurs** : nom, email, rôle, statut, dernière connexion
- **Rôles** : Administrateur, Orthodontiste, Assistant, Stagiaire
- Indicateur visuel de statut (Actif/Inactif)

---

### 9. Administration — Paramètres

![Admin Settings](maquettes/09_admin_settings.svg)

Configuration du cabinet :
- Formulaire avec champs : nom, adresse, téléphone, email, site web
- Langue par défaut, fuseau horaire
- Bouton d'enregistrement

---

## Parcours utilisateur type

1. **Connexion** → saisie identifiants
2. **Tableau de bord** → vue d'ensemble du cabinet
3. **Liste patients** → recherche du patient
4. **Détail patient** → consultation de l'historique
5. **Ajout radio** → upload d'une téléradiographie
6. **Canvas analyse** → détection des landmarks et mesures automatiques
7. **Validation** → relecture et validation par l'orthodontiste
8. **Rapport** → génération et export PDF

## Technologies cibles pour le rendu

| Élément | Technologie |
|---|---|
| Framework frontend | Jinja2 / HTMX ou React |
| Composants | Tailwind CSS + DaisyUI |
| Graphiques canvas | HTML5 Canvas + D3.js |
| Cartes/Statistiques | Chart.js |
| SVG dynamique | Manipulation DOM native |
| Export PDF | WeasyPrint |
