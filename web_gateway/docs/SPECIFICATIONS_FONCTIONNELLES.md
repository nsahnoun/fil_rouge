# Spécifications Fonctionnelles

## 1. Module Authentification

| Fonctionnalité | Rôles | Description |
|---------------|-------|-------------|
| Inscription | Tous | Création de compte avec email + mot de passe |
| Connexion | Tous | Authentification par email/mot de passe, cookie JWT HttpOnly |
| Déconnexion | Tous | Suppression du cookie de session |
| Profil | Tous | Consultation et modification du profil |
| Changement mot de passe | Tous | Vérification ancien mdp → nouveau mdp hashé |

## 2. Module Patients

| Fonctionnalité | Rôles | Description |
|---------------|-------|-------------|
| Création | Admin, Ortho, Assist | Formulaire avec identité, coordonnées, antécédents |
| Liste | Tous | Tableau paginé avec recherche |
| Détail | Tous | Fiche complète avec onglets (radios, analyses, documents, notes) |
| Modification | Admin, Ortho, Assist | Mise à jour des informations |
| Suppression | Admin | Suppression logique |
| Documents | Admin, Ortho, Assist | Upload pièces jointes |
| Notes cliniques | Admin, Ortho, Assist | Consultation, traitement, suivi, chirurgical |
| Consentement | Admin, Ortho | Traçabilité du consentement RGPD |

## 3. Module Radiographies

| Fonctionnalité | Rôles | Description |
|---------------|-------|-------------|
| Import | Admin, Ortho, Assist | Upload JPEG/PNG/DICOM |
| Liste | Tous | Par patient, avec métadonnées |
| Suppression | Admin, Ortho | Suppression sécurisée |

## 4. Module Analyses Céphalométriques

| Fonctionnalité | Rôles | Description |
|---------------|-------|-------------|
| Détection IA | Admin, Ortho | Appel à ceph_api pour détection automatique des 29 landmarks |
| Canevas interactif | Admin, Ortho | Modification manuelle des landmarks, zoom/pan, calibration |
| Calcul mesures | Admin, Ortho | 12 méthodes d'analyse : Ricketts, Steiner, Downs, Tweed, McNamara, Bjork-Jarabak, Wits, Rakosi, Segner-Hasund, Eastman, ABO, Quick |
| Validation | Admin, Ortho | Passage du statut "draft" à "validated" |
| Relecture | Admin, Ortho | Workflow de relecture par un pair |
| Comparaison | Admin, Ortho | Comparaison côte-à-côte de 2 analyses |
| Export | Admin, Ortho | PNG (image), JSON (données), PDF (rapport) |

## 5. Module Rapports

| Fonctionnalité | Rôles | Description |
|---------------|-------|-------------|
| Génération PDF | Admin, Ortho | Rapport clinique WeasyPrint |
| Templates | Admin | Personnalisation HTML/CSS des templates |
| Signature | Admin, Ortho | Signature numérique du rapport |
| Envoi | Admin, Ortho | Envoi par email au patient |

## 6. Module Administration

| Fonctionnalité | Rôles | Description |
|---------------|-------|-------------|
| Gestion utilisateurs | Admin | CRUD utilisateurs, attribution des rôles |
| Audit | Admin | Consultation et export du journal d'audit |
| Paramètres | Admin | Configuration clinique (nom, adresse, email, etc.) |

## 7. Module Tâches

| Fonctionnalité | Rôles | Description |
|---------------|-------|-------------|
| Création | Admin, Ortho, Assist | Titre, description, échéance, priorité |
| Suivi | Tous | Consultation et mise à jour du statut |

## 8. Notifications

| Fonctionnalité | Rôles | Description |
|---------------|-------|-------------|
| Réception | Tous | Alertes in-app (relecture, validation, tâche) |

## 9. Interface & Ergonomie

| Fonctionnalité | Description |
|---------------|-------------|
| Thème clair/sombre | Bascule via localStorage |
| Responsive | Adaptation mobile (≤768px) : sidebar masquée, grilles ajustées |
| Navigation | Sidebar avec sections, breadcrumbs |
| Canevas | Toolbar, sélecteur d'analyse, tracés anatomiques, table de mesures |
