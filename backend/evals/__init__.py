"""The evaluation kit of FinHelp: `python -m evals` (from backend/). See evals/README.md."""
import os
import secrets

os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(32))  # the backend settings need one; these checks sign nothing
