# Ultra Advanced Record System (Refactored)

Professional PyQt6 desktop inventory and record platform with modular architecture, analytics, reporting, and secure authentication.

## Architecture

- `main.py`: app bootstrap, dependency wiring, startup lifecycle.
- `database/`: SQLite manager, migrations, indexes, models.
- `ui/`: login/main windows, dialogs, modern QSS themes.
- `services/`: analytics, recommendations, backup, QR, reports, plugins, cloud and barcode extensions.
- `utils/`: security, validation, file safety helpers.
- `assets/`: fonts/icons/images.

## Key Upgrades

- Clean modular OOP structure with clear responsibilities.
- Role-aware auth (`admin`, `staff`, `viewer`) using bcrypt hashes.
- Dark/light theme toggle with modern QSS styles.
- Sidebar + multi-page navigation with responsive layouts.
- Smart search filters and identifier auto-complete.
- Drag-and-drop image upload and gallery page.
- Bulk CSV/Excel import and multi-sheet Excel export.
- PDF reporting with embedded analytics charts.
- Item activity timeline, overdue detection, and fine calculation support.
- Backup scheduler with async execution and status notifications.

## Run

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Launch:
   - `python main.py`

## Default Credentials

- Admin: `admin` / `admin123`
- Staff: `staff` / `staff123`

Change passwords immediately in production deployments.
