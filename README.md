# Agentic-AI-Projects
Project 1: Autonomous Disruption & Rebooking Agent (The Pilot Contract)

Target Clients: PIA, SereneAir, Airblue, Fly Jinnah.

Business Problem: Flight delays caused by weather (e.g., fog at Lahore ISB/LHE) lead to thousands of callers crashing call centers. Each unresolved ticket incurs manual processing costs and customer churn.

Contract Value: PKR 1.5M - 3M (Initial MVP) $\rightarrow$ PKR 15M+/year recurring SaaS fee once deployed.


What You Will Build (Architecture & Data Flow)

Your system receives incoming passenger queries (via WhatsApp or Web API), executes database lookups using structured tool calling, and outputs verified rebooking options.

1.Receive & Extract Intent:
Unstructured Input Processing.Extract passenger booking reference (PNR) and query intent from plain text inputs (e.g., "My flight PK302 was canceled, what are my rebooking options?").
2.Execute Tool Calls:Database & API Interrogation.The LLM triggers two deterministic python functions: lookup_pnr(pnr) to check passenger tier/baggage and check_flight_status(flight_no) to confirm cancellation state.
3.Apply Airline Rules:Deterministic Business Logic.If flight status == CANCELED, your system triggers find_available_flights(origin, destination). The Python backend filters options based on seating capacity and passenger tier.
4.Output Structured Choice:JSON Schema Enforcement.Enforce a strict JSON output returning available options, baggage migration notices, and automated confirmation links.
