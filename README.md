# CloudGuard

CloudGuard is an ESP32-based environmental monitoring and risk-detection system for flood, landslide, smoke, gas, air-quality, and related hazards. Sensor readings flow through a Flask API, are assessed by edge and server-side risk logic, stored in Firebase Realtime Database, and presented in a static operations dashboard.

## What CloudGuard Does

- Collects environmental telemetry from ESP32 sensor nodes
- Detects flood, landslide, gas, smoke, and air-quality risk
- Provides multi-device sensor APIs and historical readings
- Produces forecast and trend-based early warnings
- Supports camera-trigger events and image uploads
- Sends alert records through configured notification services
- Generates incident reports with CSV, JSON, and PDF export paths
- Displays live maps, charts, alerts, camera status, and light/dark themes

## Architecture

```text
                    +--------------------+
                    |       ESP32        |
                    |      Sensors       |
                    +---------+----------+
                              |
                              v
                    +--------------------+
                    |      Firebase      |
                    +---------+----------+
                              |
                              v
                    +--------------------+
                    |   Flask Backend    |
                    |    Risk Engine     |
                    +---------+----------+
                              |
                              v
                    +--------------------+
                    |  CloudGuard Web    |
                    |   GitHub Pages     |
                    +--------------------+
```

The backend validates readings, applies edge and server-side risk analysis, serves reports and alerts, and reads/writes Firebase data. GitHub Pages hosts only the static frontend; it does not run Flask or hold Firebase service credentials.

## Hardware

The current ESP32 configuration includes ultrasonic water-level sensing, rain, soil moisture, vibration, DHT22, BMP280, MQ-2, MQ-135, OLED, and ESP32-CAM support. MPU6050 is not part of the current implementation.

| Component | GPIO |
|---|---:|
| Ultrasonic TRIG | 18 |
| Ultrasonic ECHO | 19 |
| Rain sensor | 12 |
| Soil moisture | 35 |
| Vibration DO | 27 |
| DHT22 | 4 |
| MQ-135 | 34 |
| MQ-2 | 32 |
| OLED SDA | 21 |
| OLED SCL | 22 |

BMP280 remains supported by the firmware on its dedicated I2C bus. See [hardware/wiring/README.md](hardware/wiring/README.md) for the wiring notes.

## Software Stack

- Frontend: static HTML, CSS, and JavaScript, deployable to GitHub Pages
- Optional frontend: React and Vite under `frontend-react/`
- Backend: Python Flask with Flask-CORS
- Database: Firebase Realtime Database
- Risk and ML: Python risk engine, edge decision logic, joblib/scikit-learn boundaries, and forecast fallback
- Hardware: Arduino-compatible ESP32 C++ firmware

## Project Structure

- `frontend/`: primary static dashboard for GitHub Pages
- `frontend-react/`: preserved React/Vite implementation
- `backend/`: Flask API, services, risk analysis, Firebase integration, and training scripts
- `hardware/`: ESP32, ESP32-CAM, wiring, and protocol documentation
- `docs/`: architecture, setup, API, and hardware notes
- `tests/`: backend tests and future frontend test location
- `reports/`: generated reports kept outside source control

## Local Setup

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Configure Firebase credentials in `.env` and keep the service-account JSON outside Git. The API runs on `http://localhost:5000` by default.

### Static Frontend

For local development, serve the static frontend so browser APIs work consistently:

```powershell
cd frontend
python -m http.server 5500
```

Open `http://localhost:5500/`. Copy `config/config.example.js` to `config/config.js` and set `BACKEND_URL` to the local or deployed Flask API. Add a restricted Google Maps key only for local/deployed environments that need maps.

### React Frontend

```powershell
cd frontend-react
npm install
npm run dev
```

Set `VITE_API_BASE_URL` when the backend is not running on the local default.

## GitHub Pages Deployment

The primary `frontend/` directory is a static site. Publish that directory using GitHub Pages or a Pages workflow. Before deployment:

1. Copy `frontend/config/config.example.js` to `frontend/config/config.js` in the deployment artifact.
2. Set a restricted Google Maps key and the deployed Pages referrer.
3. Set `BACKEND_URL` in `frontend/config/config.js` to the deployed Flask API URL before publishing.
4. Ensure the backend permits the GitHub Pages origin through CORS.

Do not commit `config.js` or real keys. Restrict the Google Maps browser key to the GitHub Pages domain and enable only the required Maps APIs.

## Backend Hosting

GitHub Pages hosts static files only and cannot execute Flask or provide Firebase credentials. Deploy `backend/` separately to a Python-capable service, configure Firebase and notification secrets there, and point the frontend at that API URL.

### Render Deployment

Use the backend directory as the Render service root. Install dependencies from `requirements.txt` and use this start command:

```text
gunicorn app:app
```

The Flask application listens on Render's `PORT` environment variable when launched directly; Gunicorn binds the service port in production.

## Environment Variables

Copy `backend/.env.example` to `backend/.env` locally, or add the same variables as Render environment variables. The backend currently uses `FIREBASE_CREDENTIALS_PATH`, `FIREBASE_DATABASE_URL`, `FRONTEND_ORIGIN`, `SMS_PROVIDER`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_TEST_RECIPIENT`, `ALERT_PHONE`, `ALERT_RECIPIENTS`, `ALERT_COOLDOWN_SECONDS`, `CAMERA_COOLDOWN_SECONDS`, `CLOUDGUARD_VISION_MODEL`, `WEATHER_LATITUDE`, and `WEATHER_LONGITUDE`. Set `FRONTEND_ORIGIN` to the exact deployed frontend origin in production. Gmail variables are not used by the current backend and are intentionally not included. Keep Firebase service-account credentials, database URLs, Twilio values, alert recipients, and other secrets outside Git. Rotate credentials that appeared in the original nested project before production use.

## API

The Flask service provides health, sensor ingestion, latest/history, device, forecast, weather, camera, risk assessment, alert, report, and export endpoints. The complete route surface is documented by the running `/docs` endpoint.

## Team

Team and member details were not present in a reliable form in the audited source. Add the official SIH team name and member list here before publishing.

## Status

This is a project demonstration and development structure. Production deployment still requires authenticated device ingestion, real labeled training history, tested external notification credentials, restricted API keys, and physical hardware validation.
