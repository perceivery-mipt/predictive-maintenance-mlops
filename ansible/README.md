# Ansible Infrastructure as Code Deployment

Этот каталог содержит Infrastructure as Code слой для развёртывания MLOps-системы на одной виртуальной машине.

## Назначение

Ansible playbook автоматизирует:

1. установку базовых системных пакетов;
2. установку Docker;
3. запуск Docker service;
4. копирование проекта на VM;
5. сборку Docker images;
6. запуск PostgreSQL, Redis и MLflow;
7. запуск training pipeline;
8. promotion лучшей модели в MLflow champion;
9. запуск полного Docker Compose контура;
10. проверку health endpoints.

## Почему одна VM

По уточнению требований, микросервисы можно развернуть на одной виртуальной машине. Характеристики VM можно обосновать суммой потребления контейнеров по команде:

```bash
docker stats --no-stream
```

## Подготовка inventory

В файле `inventory.ini` нужно заменить `YOUR_VM_IP` на публичный IP виртуальной машины:

```ini
[mlops]
mlops-vm ansible_host=<PUBLIC_VM_IP> ansible_user=ubuntu
```

Проверить SSH-доступ:

```bash
ssh ubuntu@<PUBLIC_VM_IP>
```

## Запуск

Из корня проекта:

```bash
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml
```

## Проверка после деплоя

```bash
curl http://<PUBLIC_VM_IP>:8000/health
curl http://<PUBLIC_VM_IP>:5050
curl http://<PUBLIC_VM_IP>:8081/health
curl http://<PUBLIC_VM_IP>:9090/-/healthy
curl http://<PUBLIC_VM_IP>:3000/api/health
curl http://<PUBLIC_VM_IP>:9100/metrics
```

## Основные порты

```text
8000   FastAPI
5050   MLflow
8081   Airflow
9090   Prometheus
9100   Node Exporter
3000   Grafana
15432  PostgreSQL
16379  Redis
```

## Роль Docker Compose и Ansible

Docker Compose описывает состав микросервисов: PostgreSQL, Redis, MLflow, FastAPI, Airflow, Prometheus, Grafana и Node Exporter.

Ansible отвечает за подготовку виртуальной машины и воспроизводимое развёртывание проекта. Поэтому вместе Docker Compose и Ansible закрывают требование Infrastructure as Code.
