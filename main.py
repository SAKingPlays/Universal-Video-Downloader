from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from database.db_manager import DatabaseManager
from services.analytics_engine import AnalyticsEngine
from services.backup_manager import BackupManager
from services.qr_service import QRService
from services.recommendation_engine import RecommendationEngine
from ui.login_window import LoginWindow
from ui.main_window import MainWindow


def configure_logging() -> None:
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/app.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Ultra Advanced Record System")

    db = DatabaseManager("data/records.db")
    db.initialize()
    db.seed_default_users()

    analytics_engine = AnalyticsEngine(db)
    recommendation_engine = RecommendationEngine(db)
    backup_manager = BackupManager(db_path="data/records.db", backup_dir="backups")
    qr_service = QRService(output_dir="generated/qr")

    login = LoginWindow(db)
    if login.exec() != login.DialogCode.Accepted:
        return 0

    current_user = login.authenticated_user
    if current_user is None:
        return 0

    window = MainWindow(
        db=db,
        analytics_engine=analytics_engine,
        recommendation_engine=recommendation_engine,
        backup_manager=backup_manager,
        qr_service=qr_service,
        current_user=current_user,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
