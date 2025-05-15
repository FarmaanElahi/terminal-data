Here is your Unified Final PRD — incorporating all finalized architectural decisions, including Supabase Realtime for alert synchronization.

📄 Product Requirements Document (PRD)

Realtime Stock Alert Engine (Background Worker Service)

🧩 Project Title

Realtime Stock Alert Engine

🎯 Objective

Develop a high-performance, scalable, and resilient background service to monitor live stock price feeds and evaluate user-defined alerts in real time. The system is headless (no APIs), consumes real-time data, evaluates alert conditions, and pushes notifications upon triggering — all without polling APIs or user interaction.

👤 Target Users
	•	Retail investors/traders who set alerts via a frontend (e.g. Supabase UI)
	•	Alerts are configured externally and stored in Supabase/PostgreSQL

🛠️ Core Features

1. 🔔 Price Alerts
	•	Trigger when a stock’s live price crosses a user-defined threshold (up or down)
	•	Example: “Notify me when AAPL goes above $170”
	•	One-time use: disabled after triggering

2. 📉 Trendline Alerts
	•	Defined by two (timestamp, price) points forming a time-bound trendline
	•	The trendline defines a dynamic price level (linear interpolation over time)
	•	Triggers if price crosses above or below the projected trendline at the current time

🧬 Alert Lifecycle
	1.	User creates/updates alert via Supabase UI/API
	2.	Alert stored in Supabase/PostgreSQL
	3.	Background engine:
	•	Loads all untriggered alerts at startup
	•	Subscribes to Supabase Realtime for live alert changes
	•	Evaluates alerts on price ticks
	•	Dispatches notifications when alert conditions are met
	•	Removes or deactivates fired alerts

🔄 Alert Synchronization: Supabase Realtime

✅ Purpose

Keep in-memory alert list synchronized with the database without polling.

📦 Implementation
	•	Use Supabase Realtime to subscribe to changes on the alerts table
	•	Handle 3 events:
	•	INSERT: Add new alert to memory
	•	UPDATE: Update existing alert
	•	DELETE: Remove alert from memory

🔁 Fallback Plan
	•	On startup: load all untriggered alerts from DB
	•	Optional: add a periodic polling fallback if websocket fails

⚙️ System Architecture

              +-----------------------------+
              |     Supabase Frontend/API   |
              +-------------+---------------+
                            |
           [PostgreSQL via Supabase Backend]
                            |
                            ▼
          +----------------------------------------+
          |   Realtime Stock Alert Engine (Worker) |
          |----------------------------------------|
          | ✅ In-Memory Alert Store               |
          | ✅ Supabase Realtime Sync              |
          | ✅ Async Evaluator                     |
          | ✅ Async Notification Dispatcher       |
          +----------------------------------------+
                            ▲
                      Price Tick Feed (external)

🔧 Implementation Modules

Module	Purpose
alert_manager.py	Maintains symbol-indexed active alerts in memory
evaluator.py	Evaluates alerts on each price tick
dispatcher_queue.py	Async notification dispatcher with mock handler
supabase_sync.py	Subscribes to realtime DB changes (insert, update, delete)
main.py	Glue module to boot services, connect feeds, run loop

🧠 Alert State Handling
	•	Active alerts are held in memory (per symbol map)
	•	Only untriggered alerts are loaded or maintained
	•	Fired alerts are removed from memory and marked inactive in DB
	•	Trendline alert validity is time-sensitive and interpolated at runtime

🚀 Performance & Scaling Goals

Metric	Target
Max active alerts	10,000 (in-memory)
Alert eval latency	< 50 ms per tick per symbol
Notification latency	Near real-time (< 200ms dispatch)
DB sync latency	Instant via Supabase Realtime
Multi-worker support	Future via Redis + pub/sub

🔐 Reliability
	•	Stateless startup: fully recoverable via DB
	•	Realtime updates via Supabase CDC (no polling)
	•	Optionally add a reconnect/reload fallback
	•	Modular, async-based implementation (easy to maintain and extend)

🛑 Non-Goals
	•	No REST API (Supabase handles external APIs)
	•	No frontend/UI
	•	No long-term notification storage (could be added later)

🧪 Testing Support
	•	Mock price tick simulator
	•	Manual alert injection for testing scenarios
	•	Alert trigger logs
	•	Unit & integration tests for evaluator logic

🧭 Future Enhancements

Feature	Priority	Notes
Redis-based memory store	🔜	For multi-worker coordination
Notification plugin system	🔜	Email, webhook, SMS integrations
Historical logging	🧪	Audit trail of triggered alerts
Prometheus metrics	🧪	For observability and alerting
Redis streams / Kafka feed	🧪	Durable price stream ingestion

✅ Deliverables (MVP)

Deliverable	Status
In-memory alert management	✅ Done
Price/trendline alert evaluation	✅ Done
Async notification dispatcher	✅ Done
DB-backed recovery (SQLAlchemy)	✅ Done
Supabase Realtime sync	✅ Done
Ready for Docker/cron/service run	✅ Done
Redis/HA support	🔜 Future


✅ Optimization Strategy: Symbol-Scoped Subscription

🧠 Core Idea

Subscribe to real-time price ticks only for symbols that have at least one active alert in memory. Unsubscribe dynamically when there are no more alerts for that symbol.