import os
import sys
import threading
import time
from typing import List, Dict, Any, Optional

import requests

from clubtwit import ClubTwit

# Kivy UI
from kivy.app import App
from kivy.lang import Builder
from kivy.properties import ListProperty, DictProperty, StringProperty, NumericProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.utils import platform

# Optional Android-specific pieces (guarded imports)
try:
    if platform == 'android':
        from android.permissions import request_permissions, Permission
        from android.storage import primary_external_storage_path
except Exception:
    pass

KV = """
<RootView>:
    orientation: 'vertical'
    padding: '8dp'
    spacing: '8dp'

    BoxLayout:
        size_hint_y: None
        height: '42dp'
        spacing: '8dp'
        TextInput:
            id: url_input
            text: root.feed_url
            hint_text: 'Enter Club TWiT RSS URL (twitcluburl)'
            multiline: False
            on_text_validate: root.on_set_url(self.text)
        Button:
            text: 'Set URL'
            size_hint_x: None
            width: '100dp'
            on_release: root.on_set_url(url_input.text)
        Button:
            text: 'Refresh'
            size_hint_x: None
            width: '100dp'
            on_release: root.fetch_shows()

    BoxLayout:
        orientation: 'horizontal'
        spacing: '8dp'

        BoxLayout:
            orientation: 'vertical'
            size_hint_x: 0.5

            Label:
                text: 'Shows'
                size_hint_y: None
                height: '28dp'

            RecycleView:
                id: rv
                viewclass: 'ShowRow'
                data: root.rv_data
                RecycleBoxLayout:
                    default_size: None, dp(48)
                    default_size_hint: 1, None
                    size_hint_y: None
                    height: self.minimum_height
                    orientation: 'vertical'

        BoxLayout:
            orientation: 'vertical'
            size_hint_x: 0.5
            spacing: '8dp'

            Label:
                id: title_label
                text: root.selected_title
                bold: True
                size_hint_y: None
                height: '28dp'
                text_size: self.size
                halign: 'left'
                valign: 'middle'

            ScrollView:
                do_scroll_x: False
                do_scroll_y: True
                Label:
                    id: desc_label
                    text: root.selected_description
                    text_size: self.width, None
                    size_hint_y: None
                    height: self.texture_size[1]

            BoxLayout:
                size_hint_y: None
                height: '36dp'
                spacing: '8dp'
                Button:
                    id: pick_btn
                    text: 'Pick Folder'
                    on_release: root.pick_folder()
                Button:
                    id: dl_btn
                    text: 'Download'
                    disabled: not root.can_download
                    on_release: root.start_download()
                Button:
                    id: cancel_btn
                    text: 'Cancel'
                    disabled: not root.is_downloading
                    on_release: root.cancel_download()

            BoxLayout:
                size_hint_y: None
                height: '28dp'
                spacing: '8dp'
                ProgressBar:
                    id: pbar
                    max: 100
                    value: root.progress_percent
                Label:
                    id: status_label
                    text: root.status_line
                    size_hint_x: 0.6
                    text_size: self.size
                    halign: 'left'
                    valign: 'middle'

<ShowRow@BoxLayout>:
    orientation: 'horizontal'
    size_hint_y: None
    height: '48dp'
    padding: '6dp'
    spacing: '6dp'
    index: 0
    title: ''
    date: ''
    length_bytes: 0
    on_touch_up: app.root.on_select_row(self.index) if self.collide_point(*args[1].pos) else None

    Label:
        text: root.title
        halign: 'left'
        valign: 'middle'
        text_size: self.size

    Label:
        text: root.date
        size_hint_x: 0.4
        halign: 'right'
        valign: 'middle'
        text_size: self.size
"""


def _format_bytes(num_bytes: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def _format_time(seconds: float) -> str:
    try:
        import math
        if not math.isfinite(seconds) or seconds < 0:
            return "--:--"
        max_secs = 99 * 3600 + 59 * 60 + 59
        secs_f = min(float(seconds), float(max_secs))
        secs = int(secs_f + 0.5)
    except Exception:
        return "--:--"
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"


class DownloaderThread(threading.Thread):
    def __init__(self, url: str, filepath: str, progress_cb, done_cb, error_cb, stop_flag):
        super().__init__(daemon=True)
        self.url = url
        self.filepath = filepath
        self.progress_cb = progress_cb
        self.done_cb = done_cb
        self.error_cb = error_cb
        self.stop_flag = stop_flag

    def run(self):
        try:
            start_time = time.time()
            bytes_downloaded = 0
            aborted = False
            with requests.get(self.url, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                with open(self.filepath, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if self.stop_flag['stop']:
                            aborted = True
                            break
                        if not chunk:
                            continue
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        # Progress details
                        percent = int((bytes_downloaded * 100) // total_size) if total_size > 0 else 0
                        elapsed = max(time.time() - start_time, 1e-6)
                        rate = bytes_downloaded / elapsed
                        eta = ((total_size - bytes_downloaded) / rate) if (total_size > 0 and rate > 0) else -1.0
                        # Send to UI thread
                        Clock.schedule_once(lambda dt, p=percent, d=bytes_downloaded, t=total_size, r=rate, e=eta: self.progress_cb(p, d, t, r, e))

            if aborted:
                try:
                    if os.path.exists(self.filepath):
                        os.remove(self.filepath)
                except Exception:
                    pass
                Clock.schedule_once(lambda dt: self.error_cb("Canceled"))
            else:
                Clock.schedule_once(lambda dt: self.done_cb())
        except Exception as e:
            Clock.schedule_once(lambda dt, msg=str(e): self.error_cb(msg))


class RootView(BoxLayout):
    rv_data = ListProperty([])
    shows: List[Dict[str, Any]] = ListProperty([])

    selected_index = NumericProperty(-1)
    selected_title = StringProperty('')
    selected_description = StringProperty('')

    status_line = StringProperty('Ready.')
    progress_percent = NumericProperty(0)

    feed_url = StringProperty('')
    save_dir = StringProperty('')

    is_downloading = BooleanProperty(False)
    can_download = BooleanProperty(False)

    _download_thread: Optional[DownloaderThread] = None
    _stop_flag = DictProperty({'stop': False})

    def on_kv_post(self, base_widget):
        # Initialize feed_url from env if present
        self.feed_url = os.getenv('twitcluburl', '').strip()
        # Default save location
        if platform == 'android':
            try:
                base = primary_external_storage_path()
            except Exception:
                base = os.path.expanduser('~')
        else:
            base = os.path.expanduser('~')
        self.save_dir = os.path.join(base, 'Download')

        # Request permissions on Android
        if platform == 'android':
            try:
                request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
            except Exception:
                pass

        # Auto-fetch if URL available
        if self.feed_url:
            Clock.schedule_once(lambda dt: self.fetch_shows(), 0.2)

    def on_set_url(self, url: str):
        url = (url or '').strip()
        if not url:
            self.status_line = 'Please enter a valid RSS URL.'
            return
        self.feed_url = url
        # Hint for persistence on Android: Kivy Config or a small JSON file could be used
        self.status_line = 'URL set. Fetching...'
        self.fetch_shows()

    def fetch_shows(self):
        def work():
            try:
                ct = ClubTwit()
                # Override environment URL if user typed one
                if self.feed_url:
                    ct.clubtwit_url = self.feed_url
                shows = ct.fetch_shows()
                Clock.schedule_once(lambda dt: self._populate_shows(shows))
            except Exception as e:
                Clock.schedule_once(lambda dt, msg=str(e): self._show_error(msg))
        threading.Thread(target=work, daemon=True).start()
        self.status_line = 'Fetching shows...'

    def _populate_shows(self, shows: List[Dict[str, Any]]):
        self.shows = shows
        data = []
        for idx, s in enumerate(shows):
            title = s.get('Title', 'No Title')
            date = s.get('PubDate', '')
            length_bytes = s.get('Length', 0) or 0
            date_short = ' '.join(date.split()[:4]) if date else ''
            data.append({
                'index': idx,
                'title': title,
                'date': date_short,
                'length_bytes': length_bytes,
            })
        self.rv_data = data
        self.status_line = f'Loaded {len(shows)} shows.'

    def _show_error(self, msg: str):
        self.status_line = f'Error: {msg}'

    def on_select_row(self, index: int):
        if index < 0 or index >= len(self.shows):
            return
        s = self.shows[index]
        self.selected_index = index
        self.selected_title = s.get('Title', '')
        self.selected_description = s.get('Description', 'No description available.')
        self.can_download = bool(s.get('Link')) and not self.is_downloading
        self.status_line = 'Ready to download.'

    def pick_folder(self):
        # Simple folder picking strategy: ensure directory exists
        try:
            d = self.save_dir or os.path.expanduser('~')
            os.makedirs(d, exist_ok=True)
            self.status_line = f'Folder: {d}'
        except Exception as e:
            self.status_line = f'Folder error: {e}'

    def start_download(self):
        if self.is_downloading:
            return
        idx = self.selected_index
        if idx < 0 or idx >= len(self.shows):
            self.status_line = 'Select a show first.'
            return
        show = self.shows[idx]
        url = show.get('Link')
        title = show.get('Title', 'download')
        if not url:
            self.status_line = 'No download link for this item.'
            return
        safe_name = ''.join(c for c in title if c.isalnum() or c in (' ', '.', '_')).rstrip()
        ext = os.path.splitext(url)[1] or '.mp4'
        filename = safe_name + ext

        save_dir = self.save_dir or os.path.expanduser('~')
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception:
            pass
        filepath = os.path.join(save_dir, filename)

        # Start threaded download
        self.is_downloading = True
        self.can_download = False
        self.progress_percent = 0
        self.status_line = f'Downloading: {title}'
        self._stop_flag['stop'] = False

        self._download_thread = DownloaderThread(
            url=url,
            filepath=filepath,
            progress_cb=self.on_progress,
            done_cb=self.on_download_done,
            error_cb=self.on_download_error,
            stop_flag=self._stop_flag,
        )
        self._download_thread.start()

    def cancel_download(self):
        if not self.is_downloading:
            return
        self._stop_flag['stop'] = True
        self.status_line = 'Canceling download...'

    # UI thread callbacks from DownloaderThread
    def on_progress(self, percent: int, downloaded: int, total: int, rate_bps: float, eta_secs: float):
        if total > 0:
            self.progress_percent = percent
            rate_str = _format_bytes(rate_bps) + '/s' if rate_bps >= 0 else '-'
            eta_str = _format_time(eta_secs) if eta_secs >= 0 else '--:--'
            self.status_line = f"{percent}% — {rate_str} — ETA {eta_str}"
        else:
            # Unknown size
            rate_str = _format_bytes(rate_bps) + '/s' if rate_bps >= 0 else '-'
            self.status_line = f"{rate_str}"

    def on_download_done(self):
        self.is_downloading = False
        self.can_download = self.selected_index >= 0 and bool(self.shows[self.selected_index].get('Link'))
        self.progress_percent = 100
        self.status_line = 'Download complete.'

    def on_download_error(self, msg: str):
        self.is_downloading = False
        self.can_download = self.selected_index >= 0 and bool(self.shows[self.selected_index].get('Link'))
        self.status_line = f'Download failed: {msg}'


class ClubTwitAndroidApp(App):
    title = 'Club TWiT Downloader (Android)'

    def build(self):
        Builder.load_string(KV)
        return RootView()


if __name__ == '__main__':
    # Helpful if run on desktop for testing: allow setting env var via CLI
    # Usage: python android.py https://example.com/path/to/rss.xml
    if len(sys.argv) > 1 and not os.getenv('twitcluburl'):
        os.environ['twitcluburl'] = sys.argv[1]
    ClubTwitAndroidApp().run()
