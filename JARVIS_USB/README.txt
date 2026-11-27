J.A.R.V.I.S. USB — SOURCE PROJECT (WIKIPEDIA PLUGIN + HTML CLIENT)
==================================================================

WHAT THIS BUILD ADDS
--------------------
- External plugin package: Plugins/Wikipedia/manifest.json and plugin.py.
- Offline ZIM title/full-text search and article extraction using python-libzim.
- Retrieved article text is passed to the local GGUF model as reference context.
- An HTML chat interface at Web/JARVIS.html.
- A loopback-only local HTTP bridge, started by running JARVIS.exe --web.
- Launcher/Start-JARVIS-HTML.bat starts the backend and opens the browser UI.

IMPORTANT HTML LIMITATION
-------------------------
The HTML file is a browser interface, not a replacement for the local AI runtime.
It cannot directly load or execute the existing Windows JARVIS.exe or the GGUF
model by itself. The local backend must be running on the same PC. You can open
Web/JARVIS.html directly, but without the backend it can only show a connection
message. Use Launcher/Start-JARVIS-HTML.bat for the integrated HTML mode.
This does not bypass school or administrator restrictions on executable files.

WIKIPEDIA PLUGIN
----------------
Place the English Wikipedia Nopic .zim archive in Knowledge/Wikipedia. The
plugin searches for wikipedia_en_all_nopic_*.zim first, then other .zim files.
The archive must contain a search index for full-text search to work. The plugin
uses libzim, bundled into the Windows build by the GitHub Actions workflow.
If no archive or reader is available, ordinary JARVIS chat still works without
Wikipedia context. Article text is treated as untrusted reference material and
is not treated as instructions.

RUN MODES
---------
- Desktop: double-click JARVIS.exe.
- HTML: double-click Launcher/Start-JARVIS-HTML.bat.
- Browser-only HTML with no running backend is not a supported AI run mode.

BUILDING
--------
The Windows executable must be built on Windows. The included
.github/workflows/build-usb.yml uses a Windows runner to package it. This source
ZIP itself is not a prebuilt Windows executable. After a successful workflow,
copy the generated JARVIS_USB_Windows artifact contents to the USB folder.

USB SAFETY AND PORTABILITY
--------------------------
- Keep this project inside its own JARVIS_USB folder on the USB drive.
- Do NOT format the drive. Do NOT delete or overwrite unrelated USB files.
- Keep the existing Wikipedia archive, models and Piper files in their current
  matching folders when transferring the updated build.
- The app resolves paths relative to its own folder; drive-letter changes are
  supported.
- The web server binds only to 127.0.0.1 (this PC), not the local network.
- Windows may still create its own system/temp files outside this folder.

PRIVACY
-------
- No cloud inference or API keys are used.
- The HTML interface sends requests only to the local loopback backend.
- Conversation memory remains in Memory/jarvis.sqlite3.
- Push-to-talk remains available in the desktop app. The HTML interface does
  not currently provide microphone capture or Piper speech playback.

DEPENDENCIES
------------
Python 3.11 on Windows x64 for the current build workflow. python-libzim wheels
support Windows x64; see https://pypi.org/project/libzim/ and the official API
examples at https://python-libzim.readthedocs.io/.
