The code is written in python version3.12.

The requirements.txt file contains the names and versions of the python libraries

lxml==5.3.0

python-dotenv==1.0.1

requests==2.32.3

PySide6==6.7.0

You need an environment string twitcluburl containing your personal club twit url.

if you have uv you can just do a uv init to initialize then uv run main.py



Android front end (Kivy)
------------------------
A Kivy-based Android UI is available as android_app.py. It provides the same core functionality as main.py: lists shows from your RSS feed (twitcluburl), lets you select a show, and downloads it with a progress bar, rate, and ETA.

Quick desktop test
- pip install kivy requests lxml python-dotenv
- Set your feed URL via env var or pass it on the command line:
  - export twitcluburl="https://your.clubtwit/feed.xml"
  - python android_app.py
  - or: python android_app.py https://your.clubtwit/feed.xml

Android build (using Buildozer)
- Install buildozer on Linux, then run:
  - buildozer init
  - In buildozer.spec set: entrypoint = android_app.py
  - Set requirements (example): python3,kivy,requests,lxml,python-dotenv
  - Optionally set: android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
  - buildozer android debug

Notes
- The desktop requirements.txt keeps PySide6 for the desktop GUI and does not include Kivy. Install Kivy separately when testing android_app.py.
- On Android 10+ (scoped storage), saving to arbitrary folders may require SAF. By default android_app.py saves to the Download folder where possible.
- The app also respects the twitcluburl environment variable if set.



iOS front end (Kivy)
--------------------
A Kivy-based iOS UI is available as ios.py. It mirrors main.py’s functionality: lists shows from your RSS feed (twitcluburl), lets you pick a show, and downloads it with a progress bar, rate, and ETA. Files are saved to the app’s Documents folder on iOS.

Quick desktop test
- pip install kivy requests lxml python-dotenv
- Set your feed URL via env var or pass it on the command line:
  - export twitcluburl="https://your.clubtwit/feed.xml"
  - python ios.py
  - or: python ios.py https://your.clubtwit/feed.xml

iOS build (kivy-ios + Xcode)
- On macOS, install kivy-ios:
  - pipx install kivy-ios  (or: pip install kivy-ios)
- Build required recipes:
  - toolchain build python3 kivy requests lxml python-dotenv
- Create the Xcode project from your repo root:
  - toolchain create clubtwitshows-ios .
- Ensure the app entry point runs ios.py (for example, main.py in the generated app folder can do: from ios import ClubTwitiOSApp; ClubTwitiOSApp().run()).
- Open in Xcode and run:
  - toolchain open clubtwitshows-ios
  - Select a simulator or device, configure signing, and Run.

Notes
- requirements.txt is for the desktop GUI (PySide6) and does not include Kivy. Install Kivy separately when testing ios.py.
- iOS apps are sandboxed; downloads are saved to the app’s Documents folder (visible in the Files app).
- On-device, environment variables like twitcluburl are typically not present; set/override the URL in the app UI. When running on desktop, ios.py also respects the twitcluburl env var if set.
