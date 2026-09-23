# Architecture

ESP32 nodes collect sensor data and submit validated readings to the Flask backend. The backend applies edge/risk/forecast components, persists records in Firebase Realtime Database, records alerts, and exposes dashboard/report APIs. The static frontend polls those APIs and renders operations, maps, trends, camera evidence, and reports.
