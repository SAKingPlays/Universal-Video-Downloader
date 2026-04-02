"""
Modern file dialogs and folder selectors.
"""

from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QWidget
from PySide6.QtCore import Qt


class ModernFileDialog:
    """
    Wrapper for file dialogs with consistent styling.
    """
    
    @staticmethod
    def select_folder(
        parent: QWidget = None,
        title: str = "Select Download Folder",
        initial_path: str = None
    ) -> Path:
        """
        Open a folder selection dialog.
        
        Returns:
            Selected folder path or None if cancelled.
        """
        initial = initial_path or str(Path.home() / "Downloads")
        
        folder = QFileDialog.getExistingDirectory(
            parent,
            title,
            initial,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        
        return Path(folder) if folder else None
    
    @staticmethod
    def select_save_location(
        parent: QWidget = None,
        title: str = "Save File",
        initial_path: str = None,
        default_name: str = "video.mp4",
        filter_str: str = "Video Files (*.mp4 *.mkv *.webm);;All Files (*.*)"
    ) -> Path:
        """
        Open a save file dialog.
        
        Returns:
            Selected file path or None if cancelled.
        """
        initial = initial_path or str(Path.home() / "Downloads" / default_name)
        
        file_path, _ = QFileDialog.getSaveFileName(
            parent,
            title,
            initial,
            filter_str
        )
        
        return Path(file_path) if file_path else None
    
    @staticmethod
    def select_file(
        parent: QWidget = None,
        title: str = "Select File",
        initial_path: str = None,
        filter_str: str = "All Files (*.*)"
    ) -> Path:
        """
        Open a file selection dialog.
        
        Returns:
            Selected file path or None if cancelled.
        """
        initial = initial_path or str(Path.home())
        
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            title,
            initial,
            filter_str
        )
        
        return Path(file_path) if file_path else None
