JARVIS USB - MATHEMATICS + TOKEN-CONTEXT REBUILD

WHAT CHANGED
- The local llama.cpp context is explicitly set to 4,096 tokens. It no longer drops to
  2,048 merely because Windows reports RAM below 8 GB (for example, 7.8 GB).
- Before inference, JARVIS estimates the prompt token count, removes oldest history
  first, reduces retrieved reference text, and rejects an oversized request with a
  clear message instead of sending an over-context prompt to llama.cpp.
- Added an offline SymPy mathematics engine for supported symbolic and numeric tasks:
  arithmetic, equation solving, differentiation, integration, limits, factorisation,
  expansion and simplification. It uses a restricted Python-AST allow-list, not eval.
- Added SymPy, SciPy and NumPy to the Python requirements and PyInstaller collection.
- The GitHub Actions workflow builds a clean Windows onedir package and publishes
  ONLY JARVIS.exe plus the complete _internal directory.

BUILD
1. Extract the contents of the JARVIS_USB folder into the ROOT of the GitHub repository
   (so app.py, core/, requirements.txt and .github/ are at repository root).
2. Commit and push the changes to main/master, or open GitHub -> Actions ->
   "Rebuild JARVIS executable and complete internal runtime" -> Run workflow.
3. Wait for the workflow to finish successfully.
4. Download the artifact named JARVIS_EXE_and_INTERNAL_MATHS_4096.
5. Stop JARVIS on the USB. Back up the existing JARVIS.exe and _internal folder.
6. Replace ONLY JARVIS.exe and the ENTIRE _internal folder with the two items from
   the artifact. Do not delete or replace Models, Voice, Knowledge, Plugins, Config,
   Memory, Launcher, Web, or any unrelated USB files.

IMPORTANT
- This is a source/workflow package, not a prebuilt Windows executable. The actual
  JARVIS.exe and _internal are produced by the GitHub Actions Windows runner.
- The 4,096 context is a configured target. Actual memory use depends on the PC and
  model. If allocation fails on a particular machine, the runtime will report that
  separately; it will no longer silently select 2,048 based on the RAM threshold.
- The mathematics engine is a deterministic offline starting layer, not a claim that
  every university-level problem is solved. More specialised solvers can be added.
- No model file is included or changed. Existing USB data is not formatted or erased.
