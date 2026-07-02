set -euo pipefail

export AIRFLOW_HOME=~/airflow
export AIRFLOW__CORE__DAGS_FOLDER=$(pwd)/dags
export AIRFLOW__CORE__LOAD_EXAMPLES=false

mkdir -p $AIRFLOW_HOME

echo '{"admin": "admin"}' > $AIRFLOW_HOME/simple_auth_manager_passwords.json.generated

# Extra deps so the DAGs parse (docker provider) and tasks can log to
# MLflow / upload to S3 inside the Airflow tool environment.
uv tool run \
    --with apache-airflow-providers-docker \
    --with mlflow \
    --with boto3 \
    apache-airflow standalone
