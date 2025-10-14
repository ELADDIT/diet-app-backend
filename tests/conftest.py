import os
import sys
import time
import threading
from pathlib import Path

import pytest
try:  # pragma: no cover - exercised when requests is installed
    import requests  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - offline fallback
    from . import _requests_stub as requests
from werkzeug.serving import make_server


@pytest.fixture(scope="session")
def app_environment(tmp_path_factory):
    project_root = Path(__file__).resolve().parents[1]
    api_dir = project_root / "api"
    if str(api_dir) not in sys.path:
        sys.path.insert(0, str(api_dir))

    db_path = tmp_path_factory.mktemp("db") / "test.sqlite"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ.setdefault("AI_API_KEY", "test-key")
    os.environ.setdefault("AI_MODEL_NAME", "test-model")

    from app import app
    from models import Base
    from database import engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    server = make_server("127.0.0.1", 0, app)
    port = server.server_port

    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    base_url = f"http://127.0.0.1:{port}"

    timeout = time.time() + 5
    while time.time() < timeout:
        try:
            requests.get(f"{base_url}/")
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.05)
    else:
        server.shutdown()
        thread.join(timeout=1)
        raise RuntimeError("Flask test server did not start in time")

    try:
        yield {
            "base_url": base_url,
            "Base": Base,
            "engine": engine,
        }
    finally:
        server.shutdown()
        thread.join(timeout=1)


@pytest.fixture(autouse=True)
def reset_database(app_environment):
    Base = app_environment["Base"]
    engine = app_environment["engine"]
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def base_url(app_environment):
    return app_environment["base_url"]
