import sys
import os
import requests
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QPushButton, QVBoxLayout, QWidget, QHeaderView, QTextBrowser,
    QSplitter, QProgressBar, QFileDialog, QMessageBox, QInputDialog
)
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtCore import (
    Qt, QThread, QObject, Signal, Slot
)

from clubtwit import ClubTwit


class SortableTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem with a custom sort key to support numeric/date sorting."""
    def __init__(self, text: str, sort_key):
        super().__init__(text)
        self._sort_key = sort_key

    def __lt__(self, other):  # type: ignore[override]
        try:
            if isinstance(other, SortableTableWidgetItem):
                return self._sort_key < other._sort_key
        except Exception:
            pass
        return super().__lt__(other)


class ShowFetcher(QObject):
    """
    Worker object to fetch show data in a separate thread.
    """
    finished = Signal(list)
    error = Signal(str)

    def run(self) -> None:
        """
        Executes the fetching process.
        """
        try:
            ct = ClubTwit()
            if not ct.clubtwit_url:
                # Prompt user for URL if not set
                self.error.emit("NO_URL")
                return
            shows = ct.fetch_shows()
            self.finished.emit(shows)
        except Exception as e:
            self.error.emit(str(e))


class Downloader(QObject):
    """
    Worker object to download a file in a separate thread.
    """
    # Basic percentage progress for backward compatibility
    progress = Signal(int)
    # Detailed progress: percent, bytes_downloaded, total_bytes, rate_bytes_per_sec, eta_seconds
    # Use 'object' for large byte counts to avoid Qt int overflow on very large downloads.
    progress_detail = Signal(int, object, object, float, float)
    finished = Signal()
    error = Signal(str)

    def __init__(self, url: str, filepath: str):
        super().__init__()
        self.url = url
        self.filepath = filepath
        self._abort = False

    def cancel(self) -> None:
        """Requests cooperative cancellation of the download."""
        self._abort = True

    def run(self) -> None:
        """
        Executes the download process.
        """
        try:
            import time
            start_time = time.time()
            aborted = False
            with requests.get(self.url, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                bytes_downloaded = 0
                with open(self.filepath, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if self._abort:
                            aborted = True
                            break
                        if not chunk:
                            continue
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        # Calculate percentage if total size known
                        percentage = int((bytes_downloaded * 100) // total_size) if total_size > 0 else 0
                        # Calculate rate and ETA
                        elapsed = max(time.time() - start_time, 1e-6)
                        rate = bytes_downloaded / elapsed
                        eta = ((total_size - bytes_downloaded) / rate) if (total_size > 0 and rate > 0) else -1.0
                        # Emit signals
                        if total_size > 0:
                            self.progress.emit(percentage)
                        self.progress_detail.emit(percentage, bytes_downloaded, total_size, float(rate), float(eta))
            if aborted:
                # Clean up partial file
                try:
                    if os.path.exists(self.filepath):
                        os.remove(self.filepath)
                except Exception:
                    pass
                self.error.emit("Canceled")
            else:
                self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """
    The main window for the Club TWiT Downloader application.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Club TWiT Show Downloader")
        self.setGeometry(100, 100, 1200, 800)

        self.shows_data: List[Dict[str, Any]] = []
        self.current_download_title: str = ""
        # Guard to prevent slots from touching UI during/after shutdown
        self._is_shutting_down: bool = False

        # Main layout and widgets
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Splitter for table and description
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.layout.addWidget(self.splitter)

        # Table to display shows
        self._setup_table()

        # Text browser for show description
        self.description_browser = QTextBrowser()
        self.splitter.addWidget(self.description_browser)
        self.splitter.setSizes([600, 200])

        # Download/quit buttons and progress bar
        self.download_button = QPushButton("Download Selected Show")
        self.download_button.setEnabled(False)
        self.layout.addWidget(self.download_button)

        self.quit_button = QPushButton("Quit")
        self.layout.addWidget(self.quit_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)

        # Status bar
        self.statusBar().showMessage("Ready")

        # Connect signals to slots
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.download_button.clicked.connect(self.start_download)
        self.quit_button.clicked.connect(self.quit_app)

        self.load_shows()

        # Make Esc behave like Quit
        try:
            esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
            esc_shortcut.activated.connect(self.quit_app)
        except Exception:
            pass

    def _setup_table(self) -> None:
        """Initializes and configures the QTableWidget."""
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Publication Date", "Size (MB)", "Title"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTriggers.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        # Enable sorting by clicking on headers; Qt toggles order on repeated clicks
        self.table.setSortingEnabled(True)
        header.setSortIndicatorShown(True)
        # Connect to update header colors based on sorted column
        try:
            header.sortIndicatorChanged.connect(self._update_sorted_column_header_color)
        except Exception:
            pass
        # Apply initial sort: Publication Date (column 0), newest first
        try:
            header.setSortIndicator(0, Qt.SortOrder.DescendingOrder)
        except Exception:
            pass
        # Apply initial header coloring
        try:
            self._update_sorted_column_header_color()
        except Exception:
            pass
        self.splitter.addWidget(self.table)

    def load_shows(self) -> None:
        """
        Initiates fetching the show list in a background thread.
        """
        self.statusBar().showMessage("Fetching show list...")

        self.fetch_thread = QThread()
        self.fetch_worker = ShowFetcher()
        self.fetch_worker.moveToThread(self.fetch_thread)

        self.fetch_thread.started.connect(self.fetch_worker.run)
        self.fetch_worker.finished.connect(self.populate_table)
        self.fetch_worker.error.connect(self.on_fetch_error)

        self.fetch_worker.finished.connect(self.fetch_thread.quit)
        self.fetch_worker.finished.connect(self.fetch_worker.deleteLater)
        self.fetch_thread.finished.connect(self.fetch_thread.deleteLater)

        self.fetch_thread.start()

    @Slot(list)
    def populate_table(self, shows: List[Dict[str, Any]]) -> None:
        """
        Fills the table with show data received from the worker thread.
        """
        if self._is_shutting_down:
            return
        # Prevent auto-sorting jitter while filling
        was_sorting = self.table.isSortingEnabled()
        if was_sorting:
            self.table.setSortingEnabled(False)
        self.shows_data = shows
        self.table.setRowCount(len(shows))
        for row, show in enumerate(shows):
            title_text = show.get("Title") or ""
            title_item = SortableTableWidgetItem(title_text, title_text.casefold())
            title_item.setData(Qt.ItemDataRole.UserRole, show)

            pub_text = show.get("PubDate") or ""
            ts = 0.0
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(pub_text)
                if dt is not None:
                    ts = dt.timestamp()
            except Exception:
                ts = 0.0
            pub_item = SortableTableWidgetItem(pub_text, ts)

            try:
                length_bytes = int(show.get("Length", 0) or 0)
            except Exception:
                length_bytes = 0
            size_mb = f"{length_bytes / (1024 * 1024):.2f}"
            size_item = SortableTableWidgetItem(size_mb, length_bytes)

            # Set tooltips with the show's description on all cells in this row
            desc = show.get("Description") or "No description available."
            title_item.setToolTip(desc)
            pub_item.setToolTip(desc)
            size_item.setToolTip(desc)

            self.table.setItem(row, 0, pub_item)
            self.table.setItem(row, 1, size_item)
            self.table.setItem(row, 2, title_item)
        self.statusBar().showMessage(f"Loaded {len(shows)} shows.")
        if was_sorting:
            self.table.setSortingEnabled(True)
        # Ensure initial sort by Publication Date (column 0), newest first
        try:
            self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        except Exception:
            pass
        # Re-apply header color after (re)population
        try:
            self._update_sorted_column_header_color()
        except Exception:
            pass

    @Slot(str)
    def on_fetch_error(self, error_message: str) -> None:
        """
        Handles errors from the show fetching worker.
        """
        if self._is_shutting_down:
            return
        if error_message == "NO_URL":
            self.prompt_for_url()
        else:
            QMessageBox.critical(self, "Error", f"Failed to fetch shows: {error_message}")
            self.statusBar().showMessage("Error fetching shows.")

    def prompt_for_url(self) -> None:
        """
        Asks the user for their Club TWiT URL and saves it to a .env file.
        """
        url, ok = QInputDialog.getText(self, "Club TWiT URL",
                                       "Please enter your personal Club TWiT RSS feed URL:")
        if ok and url:
            with open(".env", "w") as f:
                f.write(f'twitcluburl="{url}"\n')
            self.statusBar().showMessage("URL saved. Restarting show fetch...")
            self.load_shows()  # Retry loading
        else:
            self.statusBar().showMessage("Cannot load shows without a URL.")

    @Slot()
    def on_selection_changed(self) -> None:
        """
        Updates the description and enables the download button when a show is selected.
        Also copies the episode URL to the clipboard as text.
        """
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            selected_row = selected_rows[0].row()
            title_item = self.table.item(selected_row, 2)
            show = None
            if title_item is not None:
                show = title_item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(show, dict):
                # Fallback to legacy mapping by row index
                show = self.shows_data[selected_row] if 0 <= selected_row < len(self.shows_data) else {}
            description = show.get("Description", "No description available.")
            self.description_browser.setText(description)
            # Copy URL to clipboard if available
            try:
                link = show.get("Link") if isinstance(show, dict) else None
                if link:
                    QApplication.clipboard().setText(str(link))
            except Exception:
                pass
            self.download_button.setEnabled(True)
        else:
            self.description_browser.clear()
            self.download_button.setEnabled(False)

    @Slot()
    def start_download(self) -> None:
        """
        Starts the download process for the selected show.
        """
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        selected_row = selected_rows[0].row()
        title_item = self.table.item(selected_row, 2)
        show_to_download = None
        if title_item is not None:
            show_to_download = title_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(show_to_download, dict):
            show_to_download = self.shows_data[selected_row] if 0 <= selected_row < len(self.shows_data) else None
        if not isinstance(show_to_download, dict):
            return
        download_url = show_to_download.get("Link")
        self.current_download_title = show_to_download.get("Title", "")

        if not download_url:
            QMessageBox.warning(self, "Download Error", "No download link available for this item.")
            return

        # Sanitize filename
        filename = "".join(c for c in show_to_download['Title'] if c.isalnum() or c in (' ', '.', '_')).rstrip()
        filename += os.path.splitext(download_url)[1] or ".mp4"

        save_path, _ = QFileDialog.getSaveFileName(self, "Save File", filename)

        if not save_path:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.download_button.setEnabled(False)
        self.statusBar().showMessage(f"Downloading: {show_to_download['Title']}")

        # Setup and start download thread
        self.download_thread = QThread()
        self.downloader = Downloader(download_url, save_path)
        self.downloader.moveToThread(self.download_thread)

        self.download_thread.started.connect(self.downloader.run)
        self.downloader.progress.connect(self.update_progress)
        # New detailed progress connection for rate and ETA display
        self.downloader.progress_detail.connect(self.update_progress_detail)
        self.downloader.finished.connect(self.on_download_finished)
        self.downloader.error.connect(self.on_download_error)
        # Ensure cleanup and thread exit on error as well
        self.downloader.error.connect(self.download_thread.quit)
        self.downloader.error.connect(self.downloader.deleteLater)

        self.downloader.finished.connect(self.download_thread.quit)
        self.downloader.finished.connect(self.downloader.deleteLater)
        self.download_thread.finished.connect(self.download_thread.deleteLater)

        self.download_thread.start()

    @Slot(int)
    def update_progress(self, value: int) -> None:
        """Updates the progress bar only (legacy)."""
        if self._is_shutting_down:
            return
        self.progress_bar.setValue(value)

    @Slot(int, object, object, float, float)
    def update_progress_detail(self, percent: int, downloaded: int, total: int, rate_bps: float, eta_secs: float) -> None:
        """Updates the progress bar and displays rate and ETA in the status bar."""
        if self._is_shutting_down:
            return
        # Keep the bar in sync if total known
        if total > 0:
            self.progress_bar.setValue(percent)
        # Build a friendly status string without showing downloaded size
        rate_str = self._format_bytes(rate_bps) + "/s" if rate_bps >= 0 else "-"
        if eta_secs >= 0:
            eta_str = self._format_time(eta_secs)
        else:
            eta_str = "--:--"
        if total > 0:
            status = f"Downloading: {self.current_download_title} — {percent}% — {rate_str} — ETA {eta_str}"
        else:
            status = f"Downloading: {self.current_download_title} — {rate_str}"
        self.statusBar().showMessage(status)

    def _format_bytes(self, num_bytes: float) -> str:
        """Formats a byte count into a human-readable string."""
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(num_bytes)
        for unit in units:
            if size < 1024.0 or unit == units[-1]:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"

    def _format_time(self, seconds: float) -> str:
        """Formats seconds into H:MM:SS or M:SS, guarding against overflow/non-finite values."""
        try:
            import math
            # Return placeholder for invalid or negative ETA values
            if not math.isfinite(seconds) or seconds < 0:
                return "--:--"
            # Cap to a sane upper bound to avoid absurdly large times (99:59:59)
            max_secs = 99 * 3600 + 59 * 60 + 59
            secs_f = min(float(seconds), float(max_secs))
            # Round safely without using round() on potentially huge floats
            secs = int(secs_f + 0.5)
        except Exception:
            return "--:--"
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        else:
            return f"{m}:{s:02d}"

    @Slot()
    def on_download_finished(self) -> None:
        """Handles successful download completion."""
        if self._is_shutting_down:
            return
        self.statusBar().showMessage("Download complete.")
        self.progress_bar.setVisible(False)
        self.download_button.setEnabled(True)
        QMessageBox.information(self, "Success", "The show has been downloaded successfully.")

    @Slot(str)
    def on_download_error(self, error_msg: str) -> None:
        """Handles download errors."""
        if self._is_shutting_down:
            return
        self.statusBar().showMessage("Download failed.")
        self.progress_bar.setVisible(False)
        self.download_button.setEnabled(True)
        # Avoid dialog spam on app shutdown cancel
        if error_msg != "Canceled":
            QMessageBox.critical(self, "Download Error", f"An error occurred: {error_msg}")

    @Slot()
    def quit_app(self) -> None:
        """Triggered by Quit button to close the application cleanly."""
        self.close()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Ensure background threads are terminated before closing."""
        # Mark as shutting down to prevent slots from touching the UI
        self._is_shutting_down = True
        self._shutdown_threads()
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        """Treat Esc as Quit for convenience."""
        try:
            if event.key() == Qt.Key_Escape:
                self.quit_app()
                return
        except Exception:
            pass
        super().keyPressEvent(event)

    def _update_sorted_column_header_color(self, logicalIndex: int | None = None, order: Qt.SortOrder | None = None) -> None:
        """Set the sorted column header text color to green and reset others."""
        try:
            header = self.table.horizontalHeader()
            # Determine current sorted column from header if not provided
            sorted_col = header.sortIndicatorSection()
            if sorted_col is None or sorted_col < 0:
                sorted_col = -1
            # Ensure header items exist so we can set brush
            col_count = self.table.columnCount()
            for c in range(col_count):
                item = self.table.horizontalHeaderItem(c)
                if item is None:
                    # Create a header item based on current label
                    label = self.table.model().headerData(c, Qt.Orientation.Horizontal)
                    item = QTableWidgetItem(str(label) if label is not None else "")
                    self.table.setHorizontalHeaderItem(c, item)
                # Apply color: green for sorted column, default for others
                if c == sorted_col:
                    item.setForeground(Qt.GlobalColor.green)
                else:
                    # Reset to default by clearing the brush (use black from palette role if needed)
                    item.setForeground(self.palette().windowText())
        except Exception:
            pass

    def _shutdown_threads(self) -> None:
        # Stop an active download if any
        try:
            if hasattr(self, "download_thread") and self.download_thread is not None:
                if self.download_thread.isRunning():
                    if hasattr(self, "downloader") and self.downloader is not None:
                        # Request cooperative cancellation
                        try:
                            self.downloader.cancel()
                        except Exception:
                            pass
                    # Give it some time to finish
                    self.download_thread.wait(5000)
                    if self.download_thread.isRunning():
                        # As a last resort, force terminate (unsafe, but prevents hang on exit)
                        self.download_thread.terminate()
                        self.download_thread.wait(2000)
        except Exception:
            pass

        # Try to stop fetch thread gracefully
        try:
            if hasattr(self, "fetch_thread") and self.fetch_thread is not None:
                if self.fetch_thread.isRunning():
                    self.fetch_thread.quit()
                    self.fetch_thread.wait(3000)
                    if self.fetch_thread.isRunning():
                        self.fetch_thread.terminate()
                        self.fetch_thread.wait(1000)
        except Exception:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())

