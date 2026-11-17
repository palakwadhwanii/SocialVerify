# SocialVerify Setup Guide

### 1. Setup Python AI Service
```bash
cd service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Run Python Unit Tests
```bash
cd service
PYTHONPATH=. pytest -v tests/
```

### 3. Run Benchmark Suite
```bash
cd service
PYTHONPATH=. python benchmark.py
```

### 4. Start the AI Service (Port 8010)
```bash
cd service
python app.py
```

### 5. Start Server (Port 9000)
```bash
cd server
bun install
bun run src/index.ts
```

### 6. Start Client (Port 3000)
```bash
cd client
bun install
bun run dev
```

Visit `http://localhost:3000` to interact with SocialVerify and access the **Monitoring** workspace tab.
