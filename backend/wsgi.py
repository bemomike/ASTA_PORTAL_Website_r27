import sys
import os

# ╔══════════════════════════════════════════════════════════════════╗
# ║  SATU-SATUNYA BARIS YANG PERLU DIUBAH SAAT PINDAH AKUN         ║
# ║  Ganti "mikeomed" dengan username PythonAnywhere Anda           ║
_USERNAME    = "mikeomed"                  # ← GANTI ini
_FOLDER_NAME = "ASTA_PORTAL_Website_r27"  # ← JANGAN diubah
# ╚══════════════════════════════════════════════════════════════════╝

_project_home = f"/home/{_USERNAME}/{_FOLDER_NAME}/backend"
if _project_home not in sys.path:
    sys.path.insert(0, _project_home)

from app.main import app as application
