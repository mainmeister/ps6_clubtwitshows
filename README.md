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
- Install buildozer on Linux (or via Docker). Then from the repo root:
  - Ensure you have Android SDK/NDK auto-managed by Buildozer (default) or set android.sdk_path/android.ndk_path if offline.
  - The provided buildozer.spec is already configured:
    - title = Club TWiT Downloader
    - package.name = clubtwit
    - package.domain = com.clubtwit.shows
    - android.entrypoint = android_app.py
    - requirements = python3,kivy,requests,lxml,python-dotenv
    - android.permissions include INTERNET and legacy WRITE_EXTERNAL_STORAGE (pre-Android 10)
  - Optionally export your feed URL before building (can also be set in the app UI):
    - export twitcluburl="https://your.clubtwit/feed.xml"
  - Build a debug APK:
    - buildozer android debug
  - After a successful build, the APK will be in bin/ (e.g., bin/clubtwit-0.1-arm64-v8a-armeabi-v7a-debug.apk).
  - To deploy to a connected device:
    - buildozer android deploy run logcat

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


Troubleshooting (Android Build)
------------------------------
If you see an error like:

- "Aidl not found, please install it" or in logs "Check that aidl can be executed / Aidl not found"

This means the Android SDK Build-Tools (which contain the aidl binary) are not yet installed or not found by Buildozer.

Recommended (auto-managed SDK by Buildozer):
- We’ve enabled automatic SDK license acceptance and pinned an Android API in buildozer.spec so Buildozer can install what it needs. Try again:
  - buildozer android debug

If you use a local Android SDK (custom android.sdk_path):
- Ensure Build-Tools and Platform are installed. For example (replace 33.x.x with a version you have available):
  - sdkmanager --licenses
  - sdkmanager "platform-tools" "platforms;android-33" "build-tools;33.0.2"
- In buildozer.spec, set your SDK path if you manage it yourself:
  - android.sdk_path = /path/to/Android/Sdk
- Then rebuild:
  - buildozer android debug

Notes:
- AIDL is part of the Android build-tools package. If buildozer manages the SDK, it downloads the correct build-tools automatically once licenses are accepted.
- We pinned android.api = 33 and ndk 23b which are known-good with current python-for-android.


Additional note about system AIDL vs SDK Build-Tools AIDL and auto-fix hook
---------------------------------------------------------
If you can run `aidl` at `/usr/bin/aidl`, Buildozer will still report "Aidl not found" because python-for-android relies on the AIDL binary shipped with the Android SDK Build-Tools (located under `$ANDROID_SDK/build-tools/<version>/aidl`). It does not use the system-wide `/usr/bin/aidl`.

What we changed in this repo:
- We set `android.build_tools_version = 33.0.2` in `buildozer.spec` so Buildozer installs and uses that exact Build-Tools version, ensuring the correct `aidl` is available.
- We added a p4a hook (`p4a_hook.py`) and enabled it in `buildozer.spec` so that, if AIDL is still missing in the SDK used by Buildozer, the hook will invoke `sdkmanager` to install `build-tools;33.0.2`, `platforms;android-33`, and `platform-tools` before the APK build.

If you manage your own SDK (custom `android.sdk_path`):
- Install the matching Build-Tools version and platform:
  - sdkmanager --licenses
  - sdkmanager "platform-tools" "platforms;android-33" "build-tools;33.0.2"
- In `buildozer.spec`, point to your SDK directory:
  - android.sdk_path = /home/you/Android/Sdk
- Then rebuild:
  - buildozer android debug
