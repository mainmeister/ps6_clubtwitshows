# Project Guidelines — Club TWiT Shows

## Project Overview
This repository provides tools to browse and download episodes from your private Club TWiT RSS feed. It includes:
- A desktop GUI (PySide6/Qt) for listing episodes, viewing descriptions, and downloading with progress and ETA.
- Mobile UIs built with Kivy for Android and iOS, along with build configurations (Buildozer for Android, kivy-ios/Xcode for iOS).
- Utility scripts (e.g., GetSecurityNow.py) for show-specific workflows.

The app expects your personal feed URL in the environment variable `twitcluburl`.

## Project Structure
- main.py — PySide6 desktop GUI application (entry point for desktop use).
- clubtwit.py — Core logic to fetch and parse the Club TWiT RSS feed.
- android_app.py — Kivy UI entry point for Android.
- ios.py — Kivy UI entry point for iOS.
- buildozer.spec — Android build configuration.
- p4a_hook.py — python-for-android/Buildozer helper hook (auto-installs required Android SDK components when needed).
- GetSecurityNow.py — Utility to download Security Now episodes via yt-dlp.
- README.md — Detailed usage and build notes (Android/iOS sections included).
- pyproject.toml, requirements.txt, uv.lock — Dependency declarations and lockfile.
- .junie/guidelines.md — This file with project-level instructions for Junie.

## How to Run (Desktop)
Prereqs: Python 3.12. You can use uv (recommended) or plain pip.

- Using uv
  - uv run --python 3.12 --with-requirements requirements.txt main.py
  - Or initialize the environment then run: uv run main.py
- Using pip (virtualenv recommended)
  - pip install -r requirements.txt
  - export twitcluburl="https://your.clubtwit/feed.xml"
  - python main.py

You can also pass the feed URL on the command line in the Kivy apps, or rely on the `twitcluburl` environment variable.

## Mobile Builds (Pointers)
See README.md for step-by-step instructions. Highlights:
- Android (Buildozer)
  - Entry point: android_app.py
  - build: buildozer android debug
  - The provided p4a hook can auto-install missing SDK components (build-tools, platform, platform-tools).
- iOS (kivy-ios + Xcode)
  - Entry point: ios.py
  - Build recipes with kivy-ios toolchain, create Xcode project, then run in Xcode.

## Dependencies
- Desktop GUI uses PySide6; mobile UIs use Kivy. Core logic uses requests, lxml, and python-dotenv.
- Prefer uv for reproducible runs (uv.lock present). Otherwise, use requirements.txt.

## Tests
- No automated tests are currently present. When adding tests, prefer pytest and keep them under tests/.
- For this project, Junie does not need to run tests unless they are introduced in a PR.

## Build Before Submit
- Not required for routine code/documentation changes.
- If modifying Android/iOS build files, do not run a full mobile build in CI here; just validate configurations and update README notes where necessary.

## Code Style
- Python 3.12. Keep code readable and documented with concise docstrings where helpful.
- Avoid introducing heavy dependencies. Prefer the standard library and existing stacks (PySide6/Kivy, requests, lxml, dotenv).
- Keep functions small and focused; handle errors gracefully (user-friendly messages in UIs).
- Follow simple formatting conventions (PEP 8). If in doubt, format with Black style and keep imports tidy.

## Secrets & Environment
- Never commit personal feed URLs or credentials. Use the `twitcluburl` env var locally.

## Notes for Junie
- When issues request documentation updates, prefer minimal, focused changes.
- Use the update_status tool to share findings and the plan, then implement the change.
