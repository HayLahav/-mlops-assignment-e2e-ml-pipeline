# VM setup cheat-sheet (Nebius CPU VM)

Copy-paste commands to bring the pipeline up on a fresh Ubuntu 24.04 VM.
Full context is in `README.md` (prerequisites) and `REPORT.md` (§2 triggering).

**VM spec:** 8 vCPU, 32 GB RAM, public IPv4, **100 GB SSD** boot disk
(SWE-bench pulls a multi-GB Docker image per task). No GPU needed.

---

## 1. Install tooling

```bash
# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # or: source ~/.profile

# Docker
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Use docker without sudo
sudo usermod -aG docker "$USER"
newgrp docker
docker run --rm hello-world   # sanity check
```

## 2. Clone the repo

> The repo name starts with `-`, so `cd` needs the `./` prefix or it reads the
> name as a flag.

```bash
git clone https://github.com/HayLahav/-mlops-assignment-e2e-ml-pipeline.git
cd ./-mlops-assignment-e2e-ml-pipeline
```

## 3. Configure secrets

```bash
cp .env.example .env
nano .env    # set NEBIUS_API_KEY=...  (and S3_* if using Object Storage)
```

## 4. Quick smoke test (optional but recommended)

Confirms inference + Docker work before involving Airflow.

```bash
uv sync
source .venv/bin/activate
bash scripts/mini-swe-bench-single.sh
```

## 5. Bring up Airflow + MLflow (production-style)

```bash
export HOST_PROJECT_DIR=$(pwd)
bash scripts/vm-bringup.sh
# builds mlops-assignment:latest, starts Airflow (:8080) + MLflow (:5000)
```

Get the Airflow admin password:

```bash
docker compose logs airflow | grep -i password
```

## 6. Forward ports (run on your LAPTOP, not the VM)

```powershell
ssh -L 8080:localhost:8080 -L 5000:localhost:5000 <user>@<vm-public-ip>
```

Then open http://localhost:8080 (Airflow) and http://localhost:5000 (MLflow).

## 7. Trigger a run

Airflow UI → **`evaluate_agent_docker`** → **Trigger DAG w/ config**:

```json
{"split": "test", "subset": "verified", "workers": 5,
 "model": "nebius/moonshotai/Kimi-K2.6", "task_slice": "0:3", "cost_limit": 0}
```

Watch all tasks go green. Artifacts land in `runs/<run-id>/`.

## 8. Capture deliverables

- `screenshots/airflow_dag.png` — successful DAG run
- `screenshots/mlflow_runs.png` — MLflow runs table with metrics
- `screenshots/object_storage_artifacts.png` — S3 upload (if `S3_BUCKET` set)

Inspect a finished run: `cat runs/<run-id>/manifest.json`.

---

## Standalone alternative (no Docker Compose)

```bash
uv sync
source .venv/bin/activate
bash run-airflow-standalone.sh   # Airflow on :8080, admin/admin
```
Then trigger the **`evaluate_agent`** DAG (PythonOperator path).

## Teardown

```bash
docker compose down            # stop services (keeps volumes)
docker compose down -v         # also remove Airflow/MLflow data volumes
```
