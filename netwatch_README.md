# NetWatch — Dashboard de Supervision Réseau

> Projet portfolio – Admin Système & Cybersécurité  
> Stack : Python · Flask · HTML/CSS/JS

## Présentation

NetWatch est un outil de supervision réseau léger qui surveille en temps réel l'état de machines et services : ping ICMP, scan de ports TCP, latence, et alertes visuelles. Inspiré d'EON/Nagios, développé from scratch.

## Fonctionnalités

- Monitoring en temps réel (auto-refresh toutes les 30s)
- Ping ICMP sur chaque hôte configuré
- Scan de ports TCP (HTTP, HTTPS, SSH, DNS, PostgreSQL...)
- Dashboard web responsive avec indicateurs colorés
- API REST `/api/status` (JSON) consommable par d'autres outils
- Ajout/modification des cibles via le fichier `app.py`

## Lancement

```bash
pip install -r requirements.txt
python app.py
# Ouvrir : http://localhost:5000
```

## Structure

```
netwatch/
├── app.py            # Serveur Flask + logique de monitoring
├── requirements.txt
└── README.md
```

## Améliorations possibles

- [ ] Historique des statuts (SQLite)
- [ ] Alertes par email (smtplib)
- [ ] Export CSV des logs
- [ ] Authentification basique
- [ ] Déploiement Docker

## Auteur

BEVA Jean Gynolla — M2 Informatique, ENI Fianarantsoa
