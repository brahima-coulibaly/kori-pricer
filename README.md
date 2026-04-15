# KORI Pricer Web

Application web de tarification pour **KORI TRANSPORT SA** — portage du classeur Excel
`Pricer_KT_2026_v12.xlsm` vers une application multi-utilisateurs sécurisée, hébergée
gratuitement.

## Architecture

- **Frontend/App** : [Streamlit](https://streamlit.io) (Python)
- **Backend/DB/Auth** : [Supabase](https://supabase.com) (PostgreSQL + Auth email/mot de passe + RLS)
- **Hébergement app** : [Streamlit Community Cloud](https://streamlit.io/cloud) (gratuit, HTTPS, déploiement auto depuis GitHub)

**Rôles** : Commercial • Manager • Administrateur • Consultation
(permissions appliquées via Row Level Security PostgreSQL côté Supabase)

## Déploiement (environ 30 min)

### 1. Créer un projet Supabase (gratuit)

1. Aller sur https://supabase.com → **New Project**
2. Choisir une région proche (ex. Europe West — Paris ou Frankfurt)
3. Noter le mot de passe DB et attendre la création (~2 min)
4. Menu **Project Settings → API** : copier
   - `Project URL` → servira de `SUPABASE_URL`
   - `anon` public key → servira de `SUPABASE_ANON_KEY`

### 2. Créer les tables et charger les données

Dans Supabase, ouvrir **SQL Editor** et exécuter successivement :

1. Le contenu de `supabase_schema.sql` (tables + RLS + trigger d'inscription)
2. Le contenu de `supabase_seed.sql` (74 destinations, 24 attelages, paramètres)

### 3. Configurer l'authentification

Menu **Authentication → Providers** :
- Activer **Email** (déjà actif par défaut)
- Pour la production, aller dans **Settings** et **désactiver "Confirm email"** si vous
  voulez que les comptes soient actifs immédiatement (sinon les utilisateurs doivent
  cliquer sur un lien de confirmation reçu par email).

### 4. Pousser le code sur GitHub

```bash
cd kori-pricer
git init
git add .
git commit -m "KORI Pricer v1"
# Créer un repo sur github.com puis :
git remote add origin https://github.com/<votre-compte>/kori-pricer.git
git push -u origin main
```

### 5. Déployer sur Streamlit Community Cloud

1. Aller sur https://share.streamlit.io
2. **Se connecter avec GitHub**
3. **New app** → sélectionner le repo `kori-pricer`, branche `main`, fichier `app.py`
4. Avant de cliquer **Deploy**, ouvrir **Advanced settings → Secrets** et coller :

   ```toml
   SUPABASE_URL = "https://xxxxxxxxxxxx.supabase.co"
   SUPABASE_ANON_KEY = "eyJ... (votre clé anon)"
   ```

5. **Deploy** — l'URL de votre app sera du type `https://kori-pricer.streamlit.app`

### 6. Créer le premier administrateur

1. Sur l'app déployée, onglet **Créer un compte** → s'inscrire avec votre email
2. Dans Supabase → **Table Editor → profiles** : trouver votre ligne, changer `role` de
   `consultation` à `admin`
3. Se reconnecter : vous avez maintenant accès à **Utilisateurs** et pouvez attribuer les
   rôles aux autres comptes créés.

## Développement local

```bash
python -m venv .venv
source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Éditer secrets.toml avec vos clés Supabase
streamlit run app.py
```

## Structure du projet

```
kori-pricer/
├── app.py                    # Page d'accueil + login
├── pages/                    # Pages Streamlit (auto-routing)
│   ├── 1_📝_Nouvelle_offre.py
│   ├── 2_📋_Historique.py
│   ├── 3_🗺️_Destinations.py
│   ├── 4_🚛_Véhicules.py
│   ├── 5_⚙️_Paramètres.py
│   └── 6_👥_Utilisateurs.py
├── lib/
│   ├── db.py                 # Client Supabase
│   ├── auth.py               # Authentification + rôles
│   ├── pricer.py             # Logique de calcul (formules Excel portées)
│   └── pdf.py                # Génération PDF de l'offre
├── data/                     # Seeds JSON (référence)
├── supabase_schema.sql       # À exécuter dans Supabase
├── supabase_seed.sql         # À exécuter dans Supabase après le schéma
├── requirements.txt
└── .streamlit/
    ├── config.toml
    └── secrets.toml.example
```

## Permissions par rôle

| Fonction                | Commercial | Manager | Admin | Consultation |
|-------------------------|:----------:|:-------:|:-----:|:------------:|
| Créer une offre         |     ✅     |   ✅    |  ✅   |      ❌      |
| Voir l'historique       |     ✅     |   ✅    |  ✅   |      ✅      |
| Changer statut d'offre  |     ❌     |   ✅    |  ✅   |      ❌      |
| Supprimer une offre     |     ❌     |   ✅    |  ✅   |      ❌      |
| Éditer destinations     |     ❌     |   ❌    |  ✅   |      ❌      |
| Éditer véhicules        |     ❌     |   ❌    |  ✅   |      ❌      |
| Éditer paramètres       |     ❌     |   ❌    |  ✅   |      ❌      |
| Gérer utilisateurs      |     ❌     |   ❌    |  ✅   |      ❌      |

Ces règles sont appliquées **deux fois** : côté UI (par `auth.require_role`) et côté
base de données (via les policies RLS de `supabase_schema.sql`), ce qui garantit que
même un utilisateur malveillant appelant directement l'API ne peut pas contourner les
permissions.

## Sécurité

- **HTTPS** systématique (Streamlit Cloud + Supabase).
- **Row Level Security** : chaque requête SQL est filtrée selon le rôle de l'appelant.
- Les mots de passe sont hashés par Supabase (bcrypt).
- La clé publique `anon` ne donne accès qu'à ce que les policies RLS autorisent —
  aucune clé de service n'est exposée à l'app.
- Désactivation possible de comptes sans suppression (champ `actif` dans `profiles`).

## Évolutions possibles

- Export PDF avec logo officiel et en-tête personnalisé
- Envoi de l'offre par email (Resend/SendGrid)
- Tableau de bord analytique (évolution CA, marge par destination, etc.)
- Mode hors-ligne / mobile PWA
- Sync bidirectionnel avec un classeur Excel maître
- Historique des modifications (audit log)

## Support

Pour toute question sur le portage ou l'évolution de l'application, contactez votre
équipe IT ou ouvrez une issue sur le dépôt GitHub.
