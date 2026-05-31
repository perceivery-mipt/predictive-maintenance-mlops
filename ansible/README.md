# Ansible Infrastructure as Code Deployment

Этот каталог содержит Infrastructure as Code слой для воспроизводимого развёртывания MLOps-системы predictive maintenance на одной виртуальной машине.

Ansible используется вместе с Docker Compose: Ansible подготавливает VM, копирует проект, собирает образы, запускает pipeline и проверяет сервисы; Docker Compose описывает контейнерный контур приложения и инфраструктуры.

## Назначение

Ansible playbook автоматизирует полный deployment-процесс:

1. установку базовых системных пакетов;
2. установку Docker, если Docker ещё не установлен;
3. запуск и включение Docker service;
4. добавление deployment-пользователя в группу `docker`;
5. создание удалённой директории проекта;
6. синхронизацию файлов проекта на VM;
7. сборку Docker images основного контура;
8. сборку Docker images canary-контура;
9. запуск core-инфраструктуры: PostgreSQL, Redis, MLflow;
10. запуск training pipeline и promotion лучшей модели в MLflow alias `champion`;
11. запуск полного MLOps-контура через `infra/docker-compose.yml`;
12. запуск canary inference gateway через `infra/docker-compose.canary.yml`;
13. проверку health endpoints всех ключевых сервисов;
14. smoke-test production-like inference через Feast Redis;
15. проверку canary traffic distribution.

## Почему одна VM

По требованиям задания микросервисы можно развернуть на одной виртуальной машине. 

Ресурсы VM можно обосновать суммарным потреблением контейнеров:

```bash
docker stats --no-stream
```

Для текущего проекта использовалась VM с 4 vCPU, 4 GB RAM и SSD-диском. Для стабильной работы Airflow, MLflow, Prometheus, Grafana и Docker images рекомендуется включить swap, если RAM ограничена.

## Подготовка inventory

Файл `ansible/inventory.ini` в репозитории хранится как шаблон. Перед реальным запуском deployment нужно локально указать публичный IP VM, пользователя SSH и, при необходимости, путь к приватному ключу.

Базовый вариант:

```ini
[mlops]
mlops-vm ansible_host=<PUBLIC_VM_IP> ansible_user=ubuntu

[mlops:vars]
ansible_python_interpreter=/usr/bin/python3
```

Вариант с отдельным SSH-ключом:

```ini
[mlops]
mlops-vm ansible_host=<PUBLIC_VM_IP> ansible_user=<SSH_USER> ansible_ssh_private_key_file=~/.ssh/<PRIVATE_KEY_FILE>

[mlops:vars]
ansible_python_interpreter=/usr/bin/python3
```

Проверить SSH-доступ:

```bash
ssh -i ~/.ssh/<PRIVATE_KEY_FILE> <SSH_USER>@<PUBLIC_VM_IP>
```

Проверить Ansible-доступ:

```bash
ansible -i ansible/inventory.ini mlops -m ping
```

## Запуск deployment

Из корня проекта:

```bash
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml
```

Или с временным inventory:

```bash
ansible-playbook -i /tmp/mlops-vm-inventory.ini ansible/playbook.yml
```

Успешный запуск должен завершиться без `failed` и `unreachable`:

```text
failed=0
unreachable=0
```

## Проверка после деплоя

Проверка health endpoints снаружи VM:

```bash
curl http://<PUBLIC_VM_IP>:8000/health
curl -I http://<PUBLIC_VM_IP>:5050
curl http://<PUBLIC_VM_IP>:8081/health
curl http://<PUBLIC_VM_IP>:9090/-/healthy
curl http://<PUBLIC_VM_IP>:3000/api/health
curl http://<PUBLIC_VM_IP>:9100/metrics
curl http://<PUBLIC_VM_IP>:8010/health
```

Проверка production-like inference через Feast Redis Online Store:

```bash
curl -X POST http://<PUBLIC_VM_IP>:8000/predict/from-feature-store \
  -H "Content-Type: application/json" \
  -d '{"machine_id": 1}'
```

Ожидаемый ответ содержит вероятность отказа, класс, уровень риска, рекомендуемое действие, имя модели и alias `champion`.

## Проверка контейнеров на VM

```bash
cd /opt/predictive-maintenance-mlops

docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.canary.yml ps
```

Критичные сервисы должны быть в состоянии `Up` или `Up (healthy)`.

## Основные порты

```text
8000   FastAPI inference API
8010   Canary Gateway
5050   MLflow UI
8081   Airflow UI
9090   Prometheus
9100   Node Exporter
3000   Grafana
15432  PostgreSQL
16379  Redis
```

## Роль Docker Compose и Ansible

Основной Docker Compose файл:

```text
infra/docker-compose.yml
```

Он описывает основной MLOps-контур:

- PostgreSQL — backend store для MLflow и metadata database для Airflow;
- Redis — Feast online store;
- MLflow — Tracking Server и Model Registry;
- FastAPI — online inference service;
- Airflow webserver и scheduler — orchestration;
- Prometheus — сбор метрик;
- Node Exporter — инфраструктурные метрики VM;
- Grafana — визуализация метрик.

Canary Docker Compose файл:

```text
infra/docker-compose.canary.yml
```

Он описывает canary inference contour:

- `stable` — стабильный FastAPI backend;
- `canary` — canary FastAPI backend;
- `canary-gateway` — Nginx weighted upstream gateway.

Ansible отвечает за подготовку виртуальной машины и воспроизводимое развёртывание проекта. Вместе Docker Compose и Ansible закрывают требование Infrastructure as Code.

## Canary deployment

Canary gateway доступен на порту `8010`:

```bash
curl http://<PUBLIC_VM_IP>:8010/health
```

Проверка распределения traffic:

```bash
N=50 scripts/check_canary_distribution.sh | grep deployment_track | sort | uniq -c
```

Переключение режимов выполняется скриптами:

```bash
scripts/switch_canary_90_10.sh
scripts/switch_canary_50_50.sh
scripts/switch_canary_100.sh
scripts/rollback_canary_to_stable.sh
```

## Airflow writable directories

Airflow DAG пишет данные, feature artifacts, модели и отчёты в директории проекта, смонтированные внутрь контейнера. Если task `download_data` или другая task падает с `PermissionError`, нужно проверить права на writable-директории на VM.

Команда для восстановления прав:

```bash
cd /opt/predictive-maintenance-mlops

sudo mkdir -p data/raw data/processed feature_repo/data models reports/evidently
sudo chmod -R a+rwX data feature_repo/data models reports
```

Проверка, что Airflow-контейнер может писать в `data/raw`:

```bash
docker compose -f infra/docker-compose.yml exec -T airflow-scheduler sh -c '
  touch /opt/airflow/project/data/raw/airflow_write_test.txt &&
  rm /opt/airflow/project/data/raw/airflow_write_test.txt &&
  echo airflow_can_write_data_raw_OK
'
```

## Полезные диагностические команды

Проверка состояния сервисов внутри VM:

```bash
cd /opt/predictive-maintenance-mlops

curl -s -o /dev/null -w "fastapi: %{http_code}\n" http://127.0.0.1:8000/health
curl -s -o /dev/null -w "canary: %{http_code}\n" http://127.0.0.1:8010/health
curl -s -o /dev/null -w "mlflow: %{http_code}\n" http://127.0.0.1:5050
curl -s -o /dev/null -w "airflow: %{http_code}\n" http://127.0.0.1:8081/health
curl -s -o /dev/null -w "prometheus: %{http_code}\n" http://127.0.0.1:9090/-/healthy
curl -s -o /dev/null -w "grafana: %{http_code}\n" http://127.0.0.1:3000/api/health
```

Проверка Airflow DAG runs:

```bash
docker compose -f infra/docker-compose.yml exec -T airflow-scheduler \
  airflow dags list-runs -d predictive_maintenance_training_pipeline
```

Проверка Prometheus targets:

```bash
curl "http://127.0.0.1:9090/api/v1/targets"
```

Проверка Prometheus alert rules:

```bash
curl "http://127.0.0.1:9090/api/v1/rules"
```

## Деинсталляция инфраструктуры

Остановить canary-контур:

```bash
docker compose -f infra/docker-compose.canary.yml down
```

Остановить основной контур:

```bash
docker compose -f infra/docker-compose.yml down
```

При необходимости удалить volumes:

```bash
docker compose -f infra/docker-compose.canary.yml down -v
docker compose -f infra/docker-compose.yml down -v
```
