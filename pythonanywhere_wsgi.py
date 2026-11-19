import os
import sys
from pathlib import Path


PROJECT_HOME = Path.home() / "bamexcrue-site"
if str(PROJECT_HOME) not in sys.path:
    sys.path.insert(0, str(PROJECT_HOME))

from dotenv import load_dotenv

load_dotenv(PROJECT_HOME / ".env")

from server import app, initialize_database, validate_runtime_configuration

validate_runtime_configuration()
initialize_database()
application = app
