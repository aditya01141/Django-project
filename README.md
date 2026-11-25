# NK-Bank

A Django web banking application featuring auto-provisioned 10-digit accounts, atomic peer-to-peer transfers with row-level locking, beneficiary management, charitable donations, activity search/filtering, CSV statement exports, and ReportLab PDF receipts.

## Features

- **Customer Authentication & Auto-Provisioned Accounts**: Registration automatically creates a [`BankAccount`](banking/models.py) via a `post_save` signal with a unique 10-digit account number and `$1,000.00` opening balance.
- **Dashboard & Financial Overview**: Displays account number, available balance, summary cards (Total Received, Total Sent, Total Donated, Saved Beneficiaries), search & type filters, and a unified reverse-chronological activity table.
- **Peer-to-Peer Transfers**: Select a saved beneficiary or enter a 10-digit account number manually, optionally save the recipient as a beneficiary, prevent self-transfers, and update balances inside `transaction.atomic()` with deterministic `select_for_update()` row locking.
- **Beneficiaries Management**: Add, list, quick-transfer to, and delete saved beneficiaries (`UniqueConstraint` on owner + beneficiary account).
- **Charity Donations**: Quick preset buttons (`$100`, `$250`, `$500`, `$1000`) plus custom amounts with atomic balance deduction.
- **Downloadable PDF Receipts & CSV Statements**: Server-generated `reportlab` PDF receipts for transfers and donations with strict `403 Forbidden` access control, plus filtered CSV activity exports (`/export/csv/`).

## Demo Login Credentials (Local / Seeded)

Run `python manage.py seed_demo` to initialize sample accounts and sample transactions/donations:

| Role | Username | Password | Notes |
| --- | --- | --- | --- |
| Customer 1 | `alice` | `DemoUser123!` | Includes sample transfer, donation & beneficiary |
| Customer 2 | `bob` | `DemoUser123!` | Includes sample transfer & beneficiary |
| Admin | `admin` | `AdminUser123!` | Django Admin at `/admin/` |

> **Security note:** These credentials are for local testing/demonstration only. Change passwords and set `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=False` in production.

## Local Setup (Windows / Linux / macOS)

```bash
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py seed_demo
.\venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser.

## Running Tests

```bash
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py test -v 2
```

## Hosting & Publishing

- **GitHub Pages (Static Interactive Preview)**: [docs/index.html](docs/index.html) is deployed via [.github/workflows/pages.yml](.github/workflows/pages.yml). Because GitHub Pages only hosts static HTML/CSS/JS, it runs an in-browser UI preview rather than the Python/Django backend.
  - To enable GitHub Pages in the repository: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
- **Full Live Django Backend (Render)**: Use [render.yaml](render.yaml) and [Procfile](Procfile) (`gunicorn` + `whitenoise`) to deploy the complete Django application with authentication, SQLite migrations, and ReportLab PDF receipts.

## Project Layout

```text
nkbank/             Django settings and root URL routing
banking/            Accounts, signals, atomic transfers, beneficiaries, PDF & CSV exports
donate/             Charity donations & donation PDF receipts
templates/banking/  Responsive Bootstrap 5 templates
docs/               Static GitHub Pages interactive preview
.github/workflows/  CI test runner & GitHub Pages deployment workflows
```
