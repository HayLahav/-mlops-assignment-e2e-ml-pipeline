"""Upload a finished run folder to S3-compatible Object Storage (e.g. Nebius).

Opt-in: nothing is uploaded unless ``S3_BUCKET`` is configured. Returns the
``s3://`` URI of the uploaded archive so it can be recorded in the manifest and
logged to MLflow.

Required env vars:
    S3_BUCKET                bucket name
    AWS_ACCESS_KEY_ID        access key
    AWS_SECRET_ACCESS_KEY    secret key
Optional:
    S3_ENDPOINT_URL          e.g. https://storage.eu-north1.nebius.cloud:443
    S3_PREFIX                key prefix, default "runs"
    AWS_DEFAULT_REGION       default "eu-north1"
"""

from __future__ import annotations

import os
import tarfile
import tempfile
from pathlib import Path


def _archive_run(run_dir: Path) -> Path:
    """Create a .tar.gz of the run folder in a temp location."""
    tmp = Path(tempfile.gettempdir()) / f"{run_dir.name}.tar.gz"
    with tarfile.open(tmp, "w:gz") as tar:
        tar.add(run_dir, arcname=run_dir.name)
    return tmp


def upload_run_to_s3(run_dir: Path | str, run_id: str) -> str | None:
    """Upload ``run_dir`` as a tarball. Returns the ``s3://`` URI or ``None``.

    Returns ``None`` (without raising) when storage is not configured or boto3
    is unavailable, so the pipeline still completes in local-only mode.
    """
    run_dir = Path(run_dir)
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        print("[s3] S3_BUCKET not set -- skipping upload (local artifacts only).")
        return None

    try:
        import boto3
    except ImportError:
        print("[s3] boto3 not installed -- skipping upload.")
        return None

    prefix = os.environ.get("S3_PREFIX", "runs").strip("/")
    key = f"{prefix}/{run_id}.tar.gz" if prefix else f"{run_id}.tar.gz"

    session = boto3.session.Session()
    client = session.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
        region_name=os.environ.get("AWS_DEFAULT_REGION", "eu-north1"),
    )

    archive = _archive_run(run_dir)
    try:
        client.upload_file(str(archive), bucket, key)
    finally:
        archive.unlink(missing_ok=True)

    uri = f"s3://{bucket}/{key}"
    print(f"[s3] uploaded run artifacts to {uri}")
    return uri
