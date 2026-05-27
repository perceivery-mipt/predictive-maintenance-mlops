import os
from functools import lru_cache
from pathlib import Path

from feast import FeatureStore


FEAST_REPO_PATH = os.getenv("FEAST_REPO_PATH", "feature_repo")
FEAST_REDIS_CONNECTION_STRING = os.getenv("FEAST_REDIS_CONNECTION_STRING")


@lru_cache(maxsize=1)
def get_feature_store() -> FeatureStore:
    if FEAST_REDIS_CONNECTION_STRING:
        os.environ["FEAST_REDIS_CONNECTION_STRING"] = FEAST_REDIS_CONNECTION_STRING

    repo_path = Path(FEAST_REPO_PATH)

    if not repo_path.exists():
        raise FileNotFoundError(
            f"Feast repository was not found: {repo_path}. "
            "Set FEAST_REPO_PATH or mount feature_repo into the container."
        )

    return FeatureStore(repo_path=str(repo_path))
