# 🚀 Mini DevOps Platform

> Automated Infrastructure Deployment Tool — eliminate repetitive server setup forever.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## 📋 Overview

**Mini DevOps Platform** is a Python-based CLI tool that automates complete server provisioning via SSH. One command configures a production-ready server: packages, firewall rules, Docker, application deployment, logging, and service startup — all idempotent and rollback-capable.

```
User → CLI → SSH Automation → Server Setup → Fully Configured Server
```

### Example

```bash
deploy_server --name webserver01 --type nginx --host 192.168.1.100 --user ubuntu
```

Output:

```
[✓] Connecting to 192.168.1.100...
[✓] Installing packages: nginx, curl, git, ufw...
[✓] Configuring firewall (ports 80, 443, 22)...
[✓] Installing Docker & Docker Compose...
[✓] Deploying application...
[✓] Configuring logging (rsyslog + logrotate)...
[✓] Starting & enabling services...
[✓] webserver01 is fully deployed in 47s
```

---

## 🏗️ Architecture

```
mini-devops-platform/
├── deploy_server              # CLI entry point (executable)
├── config/
│   ├── defaults.yml           # Global default settings
│   └── templates/             # Server type templates
│       ├── nginx.yml
│       ├── docker_app.yml
│       └── lamp.yml
├── src/
│   ├── cli/
│   │   └── main.py            # Click CLI definitions
│   ├── core/
│   │   ├── deployer.py        # Orchestrates full deployment
│   │   ├── ssh_client.py      # Paramiko SSH wrapper
│   │   ├── task_runner.py     # Sequential task executor
│   │   └── rollback.py        # Snapshot & rollback logic
│   ├── tasks/
│   │   ├── base.py            # Abstract task base class
│   │   ├── packages.py        # apt/yum package installation
│   │   ├── firewall.py        # UFW firewall configuration
│   │   ├── docker_task.py     # Docker + Compose setup
│   │   ├── nginx_task.py      # Nginx configuration
│   │   ├── app_deploy.py      # Application deployment
│   │   ├── logging_task.py    # rsyslog + logrotate setup
│   │   └── services.py        # systemd service management
│   ├── templates/
│   │   └── loader.py          # Jinja2 template engine
│   └── utils/
│       ├── logger.py          # Rich-powered console logger
│       └── validator.py       # Config schema validation
├── templates/                 # Jinja2 config file templates
│   ├── nginx/
│   ├── docker/
│   ├── logging/
│   └── systemd/
└── tests/                     # pytest test suite
```

---

## ⚙️ Installation

### Prerequisites

- Python 3.9+
- SSH access to target server (key-based auth recommended)

### Install

```bash
git clone https://github.com/yourname/mini-devops-platform.git
cd mini-devops-platform
pip install -e .
```

Or with pipx (recommended for CLI tools):

```bash
pipx install .
```

### Verify

```bash
deploy_server --version
```

---

## 🚦 Quick Start

### 1. Configure your server

```yaml
# myserver.yml
name: webserver01
host: 192.168.1.100
user: ubuntu
key_file: ~/.ssh/id_rsa
server_type: nginx
packages:
  - nginx
  - curl
  - git
ports:
  - 80
  - 443
  - 22
app:
  repo: https://github.com/yourname/your-app.git
  branch: main
  deploy_path: /var/www/myapp
```

### 2. Deploy

```bash
# From a YAML config file
deploy_server --config myserver.yml

# Or inline via CLI flags
deploy_server \
  --name webserver01 \
  --type nginx \
  --host 192.168.1.100 \
  --user ubuntu \
  --key ~/.ssh/id_rsa \
  --ports 80,443

# Dry run (no changes made)
deploy_server --config myserver.yml --dry-run

# With verbose output
deploy_server --config myserver.yml --verbose
```

---

## 📦 Server Type Templates

| Template      | Packages Installed         | Ports | Description              |
|---------------|---------------------------|-------|--------------------------|
| `nginx`       | nginx, curl, ufw           | 80, 443, 22 | Static/reverse proxy |
| `docker_app`  | docker, docker-compose     | 80, 443, 22 | Containerised app    |
| `lamp`        | apache2, mysql, php        | 80, 443, 22, 3306 | LAMP stack      |

---

## 🔄 Rollback

Every deployment creates a snapshot before execution. Roll back instantly:

```bash
# List snapshots for a server
deploy_server rollback --name webserver01 --list

# Rollback to a specific snapshot
deploy_server rollback --name webserver01 --snapshot 20240115_143022
```

---

## 🧪 Testing

```bash
# Run all tests
make test

# With coverage
make coverage

# Lint
make lint
```

---

## 📖 Documentation

- [Architecture Deep Dive](docs/architecture.md)
- [Adding Custom Tasks](docs/custom_tasks.md)
- [Configuration Reference](docs/configuration.md)

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-task`
3. Commit: `git commit -m 'feat: add my task'`
4. Push: `git push origin feature/my-task`
5. Open a Pull Request

---

## 📄 License

MIT © 2024
