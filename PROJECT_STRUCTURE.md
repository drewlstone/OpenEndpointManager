# Project Structure

Complete file tree for PolyProv v0.1.0. Generated at release.

```
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── deps.py
│   │   ├── devices.py
│   │   ├── reports.py
│   │   └── users.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── logging_config.py
│   │   ├── metrics.py
│   │   ├── redis_client.py
│   │   └── security.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── config.py
│   │   ├── device.py
│   │   └── org.py
│   ├── provisioning/
│   │   ├── __init__.py
│   │   ├── renderer.py
│   │   ├── resolver.py
│   │   └── router.py
│   ├── schemas/
│   │   └── __init__.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── device_import.py
│   │   └── firmware_resolver.py
│   ├── __init__.py
│   ├── main.py
│   └── worker.py
├── deploy/
│   ├── docker/
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   ├── k8s/
│   │   ├── helm/
│   │   │   ├── templates/
│   │   │   │   └── NOTES.txt
│   │   │   ├── Chart.yaml
│   │   │   └── values.yaml
│   │   └── manifests.yaml
│   └── grafana-dashboard.json
├── docs/
│   ├── dhcp/
│   │   └── README.md
│   ├── ARCHITECTURE.md
│   └── load-test-plan.md
├── migrations/
│   ├── versions/
│   │   └── .gitkeep
│   ├── env.py
│   ├── partitioning.sql
│   └── script.py.mako
├── nginx/
│   ├── admin.conf
│   ├── provisioning.conf
│   └── ui.conf
├── provisioning_root/
│   ├── configs/
│   │   ├── 000000000000.cfg
│   │   ├── 0004f2aabbcc.cfg
│   │   └── sip-global.cfg
│   └── firmware/
│       └── ccx/
│           └── .gitkeep
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_mac.py
│   ├── test_renderer.py
│   └── test_resolver.py
├── tools/
│   ├── seed.py
│   └── simulator.py
├── ui/
│   ├── public/
│   │   └── .gitkeep
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api.js
│   │   │   └── ui.jsx
│   │   ├── pages/
│   │   │   ├── Checkins.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── DeviceDetail.jsx
│   │   │   ├── Devices.jsx
│   │   │   ├── Firmware.jsx
│   │   │   ├── Groups.jsx
│   │   │   ├── Health.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── ProvLogs.jsx
│   │   │   ├── Rollouts.jsx
│   │   │   ├── Sites.jsx
│   │   │   ├── Templates.jsx
│   │   │   ├── Tenants.jsx
│   │   │   └── Users.jsx
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── .dockerignore
│   ├── Dockerfile
│   ├── README.md
│   ├── index.html
│   ├── nginx-ui.conf
│   ├── package.json
│   └── vite.config.js
├── .dockerignore
├── .env.example
├── .gitignore
├── API_REFERENCE.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── DEPLOYMENT.md
├── INSTALL.md
├── LICENSE
├── OPERATIONS.md
├── PROJECT_STRUCTURE.md
├── README.md
├── ROADMAP.md
├── SECURITY.md
├── TROUBLESHOOTING.md
├── alembic.ini
├── pytest.ini
└── requirements.txt
```

Total: 103 files.
