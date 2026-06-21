# Schéma de base de données — AI Studio Pro

Le projet utilise des modèles SQLAlchemy. En développement, SQLite peut être utilisé. En production, PostgreSQL est recommandé.

## Entités principales

| Table | Rôle |
|---|---|
| `users` | Comptes utilisateurs, rôles, profil, crédits. |
| `refresh_tokens` | Allowlist des refresh tokens si activée. |
| `credit_wallets` | Solde de crédits par utilisateur. |
| `credit_transactions` | Ledger des mouvements de crédits. |
| `stripe_payments` | Sessions et paiements Stripe. |
| `webhook_events` | Idempotence et suivi des webhooks. |
| `generations` | Requêtes et résultats de génération. |
| `support_tickets` | Réclamations et support. |
| `audit_logs` | Historique des actions sensibles si activé. |

## Règles métier importantes

- Une génération doit vérifier le solde avant exécution.
- Le débit des crédits doit être transactionnel.
- Les webhooks Stripe doivent être idempotents.
- Un administrateur hérite des fonctionnalités utilisateur et ajoute les fonctionnalités d'administration.
- Les résultats intermédiaires Image-to-Image ne doivent pas être retournés comme résultat final.

## Recommandation production

- PostgreSQL avec migrations.
- Index sur `user_id`, `created_at`, `status`, `event_id` et `jti`.
- Sauvegardes régulières.
- Pas de secrets dans la base sauf nécessité, et jamais en clair.
