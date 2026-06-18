# Database Schema

This project uses SQLAlchemy models with an async engine.

## Main entities
- **users**: accounts, roles, credits, tier
- **subscriptions**: subscription history and current_period_end (UTC datetime)
- **payments**: Stripe sessions and succeeded payments
- **generations**: user generation requests, status, output URL
- **credit_transactions**: full ledger of credit movements
- **webhook_events**: idempotency/processing tracking for webhook events

See the ER diagram: `assets/er_diagram.png`.
