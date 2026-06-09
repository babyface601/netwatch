# 📡 NetWatch — Dashboard de Supervision Réseau

![CI](https://github.com/babyface601/netwatch/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.3+-000000?logo=flask)
![License](https://img.shields.io/badge/Licence-MIT-green)

NetWatch est une application web de monitoring réseau en temps réel, construite avec **Python/Flask**. Elle scanne des hôtes (ping + ports TCP), affiche leur état dans un dashboard, conserve un historique et envoie des alertes lors de changements d'état.

---

## 📸 Aperçu

![Dashboard NetWatch](docs/screenshot.png)

---

## ✨ Fonctionnalités

- **Scan en temps réel** — ping et vérification de ports TCP en parallèle (ThreadPoolExecutor)
- **Dashboard web** — interface sombre responsive, mise à jour automatique toutes les 30 secondes
- **Gestion des hôtes** — ajout et suppression d'hôtes directement depuis l'interface
- **Historique SQLite** — chaque scan est sauvegardé, avec visualisation des 20 derniers résultats par hôte
- **Alertes** — détection des changements d'état (up ↔ down), log console + email optionnel (SMTP)
- **Authentification** — login/logout par session Flask, identifiants configurables
- **Configuration externe** — cibles définies dans `targets.json`, modifiable sans toucher au code

---

## 🖥️ Interface

```
┌─────────────────────────────────────────┐
│  📡 NetWatch   Dashboard de Supervision  │
│                          ↻ Actualiser   │
├──────────┬──────────┬────────┬──────────┤
│ Total: 7 │ En ligne │ Hors   │ Dispo:   │
│          │    5     │ ligne 2│  71%     │
├─────────────────────────────────────────┤
│ ■ Google DNS  UP    53ms  ● :53         │
│ ■ GitHub      UP   142ms  ● :443 ● :22 │
│ ■ PostgreSQL  DOWN   —    ○ :5432       │
│ ...                                     │
├─────────────────────────────────────────┤
│ Historique des scans                    │
│ Google DNS   100%  ■■■■■■■■■■■■■■■■■■■■│
│ GitHub        95%  ■■■■■■■■■■■■■■■■□■■■│
└─────────────────────────────────────────┘
```

---

## 🚀 Installation

### Prérequis
- Python 3.8+
- pip

### Étapes

```bash
# 1. Cloner le repo
git clone https://github.com/babyface601/netwatch.git
cd netwatch

# 2. Installer les dépendances
pip install -r netwatch_requirements.txt

# 3. Lancer l'application
python netwatch_app.py
```

Ouvre **http://localhost:5000** dans ton navigateur.
Login par défaut : `admin` / `netwatch`

---

## ⚙️ Configuration

### Identifiants et sécurité

```bash
# Windows (cmd)
set NETWATCH_USER=admin
set NETWATCH_PASSWORD=monmotdepasse
set SECRET_KEY=une-cle-secrete-aleatoire

# Linux / macOS
export NETWATCH_USER=admin
export NETWATCH_PASSWORD=monmotdepasse
export SECRET_KEY=une-cle-secrete-aleatoire
```

### Alertes email (optionnel)

```bash
set SMTP_HOST=smtp.gmail.com
set SMTP_PORT=587
set SMTP_USER=toi@gmail.com
set SMTP_PASS=ton_app_password
set ALERT_TO=destinataire@gmail.com
```

> Sans configuration SMTP, les alertes apparaissent uniquement dans les logs console.

### Ajouter des hôtes à surveiller

Modifie `targets.json` :

```json
[
  {"name": "Mon serveur", "host": "192.168.1.10", "ports": [80, 443], "type": "web"},
  {"name": "Ma base",     "host": "127.0.0.1",    "ports": [5432],    "type": "db"}
]
```

Ou utilise le bouton **+ Ajouter** directement dans l'interface.

---

## 🗂️ Structure du projet

```
netwatch/
├── netwatch_app.py              # Serveur Flask (backend)
├── targets.json                 # Configuration des hôtes
├── netwatch_requirements.txt    # Dépendances Python
├── .gitignore
└── templates/
    ├── dashboard.html           # Interface principale
    └── login.html               # Page de connexion
```

---

## 🛠️ Stack technique

| Couche | Technologie |
|---|---|
| Backend | Python 3, Flask |
| Scan réseau | `socket`, `subprocess` (ping) |
| Concurrence | `ThreadPoolExecutor` |
| Base de données | SQLite (`sqlite3` — stdlib) |
| Alertes email | `smtplib` + `MIMEText` (stdlib) |
| Auth | Flask sessions |
| Frontend | HTML5, CSS3, JavaScript vanilla |

---

## 📄 Licence

MIT — libre d'utilisation et de modification.
