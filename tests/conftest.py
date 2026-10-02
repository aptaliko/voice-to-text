import os
import tempfile

os.environ.setdefault("APP_USERNAME", "user")
os.environ.setdefault("APP_PASSWORD", "secret")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="vtt-test-"))
os.environ.setdefault("MAX_UPLOAD_MB", "1")
