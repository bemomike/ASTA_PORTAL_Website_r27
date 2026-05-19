import sys
import os

# ── Path ke folder backend di PythonAnywhere ──────────────────────────────────
# Sesuaikan nama folder jika berbeda dari ASTA_PORTAL_r26
# Contoh jika folder di-upload dengan nama asli: /home/mikeomed/ASTA_PORTAL_r26/backend
# Contoh jika tetap pakai nama lama:             /home/mikeomed/ASTA_PORTAL_Website_r24/backend
_project_home = "/home/mikeomed/ASTA_PORTAL_r26/backend"
if _project_home not in sys.path:
    sys.path.insert(0, _project_home)

from app.main import app as application
