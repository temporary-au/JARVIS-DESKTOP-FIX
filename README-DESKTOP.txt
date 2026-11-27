J.A.R.V.I.S. DESKTOP EDITION — SOURCE BUILD
==========================================

This archive contains desktop source code and a nested, separate USB source tree.
It is NOT a prebuilt Windows executable. The Windows GitHub Actions workflow
produces the onedir application package. A successful source test is not proof
that the Windows GUI, model inference, microphone or USB split-off has passed.

INSTALLATION ROOT AND WRITE ISOLATION
- Keep the complete JARVIS_Desktop folder together.
- All application-managed writable data is rooted beneath this folder: Data,
  Temp, Models, Voice, Knowledge, Logs and configuration.
- There is deliberately no AppData/Documents/Desktop/Temp fallback. If the
  folder is not writable, the operation must fail and report the error.
- No environment variable can redirect the application data root.
- The nested JARVIS_USB folder is the independent USB source tree. Desktop
  maintenance may edit it, but the desktop app must not silently change its
  data or runtime configuration.
- The USB edition must be copied to a separate test directory and verified
  independently before it is declared portable.

AI MODES (16 GB RAM, integrated graphics target)
- Intelligent: Meta Llama 3.1 8B Instruct Q4_K_M. Highest reasoning mode in
  this initial hardware tier; CPU-first and potentially slow.
- Balanced: Gemma 3 4B IT Q4_K_M. Default balance of capability and speed.
- Speed: SmolLM2 1.7B Instruct Q4_K_M. Lightweight response mode.
- Each mode requires its exact GGUF file in Models. Only one model is loaded
  at a time. Desktop modes do not silently fall back to the USB Qwen model.
- Model file sizes and performance depend on the exact GGUF quantisation/build.
  Benchmark on the target HP laptop before treating the model choices as final.

MEMORY
- The Memory page reads all rows from the active SQLite conversation store,
  supports search, edit and confirmed deletion. It is not a sample-data panel.
- Conversation memory is distinct from a future semantic long-term memory
  system; this build's manager exposes the complete stored message history.

KNOWLEDGE
- The current included retrieval plugin is offline Wikipedia via a compatible
  ZIM archive. Additional document ingestion and a general multi-source
  retrieval index are not yet complete in this source snapshot.
- Do not assume PDF/DOCX/CSV import, source citations, health checks or
  resumable indexing are implemented until their tests and UI are added.

BUILD AND TEST
- Run: python -m compileall -q app.py core tests
- Run: python -m unittest discover -s tests -v
- Then run the Windows workflow and test the resulting package on Windows.
- Do not call the desktop or nested USB edition fully verified until runtime,
  relocation, write-boundary, UI, voice, knowledge and standalone USB tests pass.
