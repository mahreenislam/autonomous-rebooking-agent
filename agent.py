import os
import sys
import time
import json
import sqlite3
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Ensure standard streams handle UTF-8 properly on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "airline_pss.db")
SQLITE_TIMEOUT = 10.0


# ============================================================================
# 1. Production-Ready Tool Functions (Read & Action/Write Execution)
# ============================================================================

def check_flight_status(flight_number: str) -> str:
    """
    Queries real-time status, route, departure time, and delay/cancellation reason for a given flight number.
    """
    if not flight_number or not isinstance(flight_number, str):
        return json.dumps({"status": "error", "message": "A valid flight number must be provided."})

    flight_clean = flight_number.strip().upper()
    print(f"  -> [TOOL] Checking status for flight '{flight_clean}'...", flush=True)

    try:
        with sqlite3.connect(DB_PATH, timeout=SQLITE_TIMEOUT) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT flight_number, origin, destination, status, departure_time, reason FROM flights WHERE flight_number = ?",
                (flight_clean,)
            )
            row = cursor.fetchone()

            if row:
                return json.dumps({
                    "status": "success",
                    "flight_number": row[0],
                    "origin": row[1],
                    "destination": row[2],
                    "flight_status": row[3],
                    "departure_time": row[4],
                    "reason": row[5]
                })
            return json.dumps({
                "status": "error",
                "message": f"Flight '{flight_clean}' was not found in the flight schedules database."
            })
    except sqlite3.OperationalError as e:
        return json.dumps({"status": "error", "message": f"Database lock/operational error: {str(e)}"})
    except sqlite3.Error as e:
        return json.dumps({"status": "error", "message": f"Database query error: {str(e)}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Unexpected error checking flight: {str(e)}"})


def lookup_passenger_pnr(pnr_code: str) -> str:
    """
    Retrieves passenger name, assigned flight, loyalty tier, baggage count, and booking status for a given PNR.
    """
    if not pnr_code or not isinstance(pnr_code, str):
        return json.dumps({"status": "error", "message": "A valid PNR code must be provided."})

    pnr_clean = pnr_code.strip().upper()
    print(f"  -> [TOOL] Looking up reservation for PNR '{pnr_clean}'...", flush=True)

    try:
        with sqlite3.connect(DB_PATH, timeout=SQLITE_TIMEOUT) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT pnr, passenger_name, flight_number, tier, checked_bags, status FROM bookings WHERE pnr = ?",
                (pnr_clean,)
            )
            row = cursor.fetchone()

            if row:
                return json.dumps({
                    "status": "success",
                    "pnr": row[0],
                    "passenger_name": row[1],
                    "assigned_flight": row[2],
                    "tier": row[3],
                    "checked_bags": row[4],
                    "booking_status": row[5]
                })
            return json.dumps({
                "status": "error",
                "message": f"PNR '{pnr_clean}' was not found in the passenger reservation system."
            })
    except sqlite3.OperationalError as e:
        return json.dumps({"status": "error", "message": f"Database lock/operational error: {str(e)}"})
    except sqlite3.Error as e:
        return json.dumps({"status": "error", "message": f"Database query error: {str(e)}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Unexpected error looking up PNR: {str(e)}"})


def fetch_alternative_flights(origin: str, destination: str) -> str:
    """
    Finds all active, on-time alternative flights between a specific origin and destination airport code.
    """
    if not origin or not destination:
        return json.dumps({"status": "error", "message": "Both origin and destination codes are required."})

    origin_clean = origin.strip().upper()
    dest_clean = destination.strip().upper()
    print(f"  -> [TOOL] Searching alternative flights for route {origin_clean} -> {dest_clean}...", flush=True)

    try:
        with sqlite3.connect(DB_PATH, timeout=SQLITE_TIMEOUT) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT flight_number, departure_time FROM flights WHERE origin = ? AND destination = ? AND status = 'ON_TIME'",
                (origin_clean, dest_clean)
            )
            rows = cursor.fetchall()

            options = [{"flight_number": r[0], "departure_time": r[1]} for r in rows]
            return json.dumps({
                "status": "success",
                "origin": origin_clean,
                "destination": dest_clean,
                "available_alternatives": options,
                "count": len(options)
            })
    except sqlite3.OperationalError as e:
        return json.dumps({"status": "error", "message": f"Database lock/operational error: {str(e)}"})
    except sqlite3.Error as e:
        return json.dumps({"status": "error", "message": f"Database query error: {str(e)}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Unexpected error fetching alternatives: {str(e)}"})


def rebook_passenger(pnr_code: str, new_flight_number: str) -> str:
    """
    Executes a database write action to rebook a passenger onto a new flight.
    Validates booking existence, verifies that the new flight is active and on-time,
    and updates the reservation status to REBOOKED.
    """
    if not pnr_code or not new_flight_number:
        return json.dumps({"status": "error", "message": "Both PNR code and new flight number are required for rebooking."})

    pnr_clean = pnr_code.strip().upper()
    flight_clean = new_flight_number.strip().upper()
    print(f"  -> [TOOL ACTION] Rebooking PNR '{pnr_clean}' to new flight '{flight_clean}'...", flush=True)

    try:
        with sqlite3.connect(DB_PATH, timeout=SQLITE_TIMEOUT) as conn:
            cursor = conn.cursor()

            # Step 1: Validate passenger booking exists
            cursor.execute(
                "SELECT passenger_name, flight_number, checked_bags, tier FROM bookings WHERE pnr = ?",
                (pnr_clean,)
            )
            booking = cursor.fetchone()
            if not booking:
                return json.dumps({
                    "status": "error",
                    "message": f"Cannot rebook: PNR '{pnr_clean}' does not exist in bookings."
                })

            passenger_name, old_flight, checked_bags, tier = booking

            # Step 2: Validate new flight exists and is ON_TIME
            cursor.execute(
                "SELECT status, departure_time, origin, destination FROM flights WHERE flight_number = ?",
                (flight_clean,)
            )
            flight_info = cursor.fetchone()
            if not flight_info:
                return json.dumps({
                    "status": "error",
                    "message": f"Cannot rebook: New flight '{flight_clean}' does not exist in the schedule."
                })

            flight_status, departure_time, origin, destination = flight_info
            if flight_status != "ON_TIME":
                return json.dumps({
                    "status": "error",
                    "message": f"Cannot rebook: Selected flight '{flight_clean}' is currently '{flight_status}' and not available for rebooking."
                })

            # Step 3: Perform atomic database update
            cursor.execute(
                "UPDATE bookings SET flight_number = ?, status = 'REBOOKED' WHERE pnr = ?",
                (flight_clean, pnr_clean)
            )
            conn.commit()

            return json.dumps({
                "status": "success",
                "message": f"Passenger {passenger_name} successfully rebooked to flight {flight_clean}.",
                "pnr": pnr_clean,
                "passenger_name": passenger_name,
                "tier": tier,
                "previous_flight": old_flight,
                "new_flight": flight_clean,
                "departure_time": departure_time,
                "route": f"{origin} -> {destination}",
                "baggage_transferred": checked_bags,
                "booking_status": "REBOOKED"
            })
    except sqlite3.OperationalError as e:
        return json.dumps({"status": "error", "message": f"Database lock/concurrency error during rebooking: {str(e)}"})
    except sqlite3.Error as e:
        return json.dumps({"status": "error", "message": f"Database error during rebooking: {str(e)}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Unexpected error during rebooking: {str(e)}"})


# ============================================================================
# 2. Production Agent Class
# ============================================================================

SYSTEM_INSTRUCTION = """
You are an expert autonomous airline disruption and customer support agent.
Your primary responsibility is to resolve passenger flight disruptions promptly, accurately, and politely.

Standard Operating Protocol:
1. Passenger Verification:
   - When a passenger reaches out, first lookup their PNR using `lookup_passenger_pnr` to retrieve their name, booked flight, and baggage details.
2. Disruption Verification:
   - Check the status of their assigned flight using `check_flight_status`.
   - If the flight is CANCELED or severely delayed, fetch viable alternative on-time flights on the same route using `fetch_alternative_flights`.
3. Presenting Options:
   - Present available rebooking options clearly with departure times.
   - Reassure the passenger that their checked bags will be automatically transferred to whichever flight they choose.
4. Action Execution (Rebooking):
   - When the passenger confirms or selects a specific flight, call `rebook_passenger` with their PNR and chosen flight number.
   - Provide an explicit confirmation summary with the new flight number, departure time, and baggage transfer status.
5. Error Handling:
   - If a database lookup or rebooking tool returns an error, explain the issue transparently and provide helpful next steps.
"""

class AirlineDisruptionAgent:
    """Manages the lifecycle, tool registry, and multi-turn conversational session of the agent."""
    def __init__(self, model: str = "gemini-3.5-flash-lite"):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set. Please check your .env file.")

        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.chat = self.client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[
                    check_flight_status,
                    lookup_passenger_pnr,
                    fetch_alternative_flights,
                    rebook_passenger
                ],
                temperature=0.1
            )
        )

    def send_message(self, message: str, max_retries: int = 3) -> str:
        """Sends a message to the agent with automatic rate limit backoff and returns its text response."""
        for attempt in range(max_retries):
            try:
                response = self.chat.send_message(message)
                return response.text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait_time = 35 + (attempt * 10)
                    print(f"\n[Rate Limit pause: waiting {wait_time}s before automatic retry ({attempt + 1}/{max_retries})...]", flush=True)
                    time.sleep(wait_time)
                else:
                    raise e
        raise RuntimeError("Exceeded maximum retries due to rate limit restrictions.")


# ============================================================================
# 3. Conversational Multi-Turn Handlers (Interactive CLI & Automated Demo)
# ============================================================================

def interactive_chat_session():
    """Starts an interactive multi-turn terminal session."""
    print("=" * 70, flush=True)
    print("AIRLINE DISRUPTION AGENT (Production Multi-Turn CLI)", flush=True)
    print("Type your message below. Type 'exit' or 'quit' to end the session.", flush=True)
    print("=" * 70, flush=True)

    try:
        agent = AirlineDisruptionAgent()
    except Exception as e:
        print(f"Failed to initialize agent: {e}", flush=True)
        return

    while True:
        try:
            user_input = input("\n[Passenger]: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("\nSession ended. Have a safe journey!", flush=True)
                break

            print("\n[Agent is processing...]", flush=True)
            response_text = agent.send_message(user_input)
            print(f"\n[Agent]:\n{response_text}\n", flush=True)
            print("-" * 70, flush=True)
        except KeyboardInterrupt:
            print("\n\nSession terminated by user.", flush=True)
            break
        except Exception as e:
            print(f"\n[Error during conversation turn]: {e}", flush=True)


def run_demo_multiturn():
    """Runs an automated multi-turn conversation demo to verify state retention and rebooking."""
    print("=" * 70, flush=True)
    print("RUNNING MULTI-TURN PRODUCTION DEMO TEST", flush=True)
    print("=" * 70, flush=True)

    agent = AirlineDisruptionAgent()

    turns = [
        # Turn 1: Initial disruption query
        "Passenger PNR PK-88912 says: 'My flight PK302 was canceled due to fog! What are my rebooking options and what happens to my 2 bags?'",
        
        # Turn 2: Passenger selects an alternative flight (relies on conversation memory)
        "Please book me on flight PK304."
    ]

    for turn_idx, turn_msg in enumerate(turns, 1):
        print(f"\n[TURN {turn_idx} - PASSENGER]: {turn_msg}", flush=True)
        print("-" * 60, flush=True)
        response_text = agent.send_message(turn_msg)
        print(f"\n[AI AGENT RESPONSE]:\n{response_text}", flush=True)
        print("=" * 70, flush=True)


if __name__ == "__main__":
    # If '--interactive' or '-i' argument is passed, launch interactive chat loop
    if len(sys.argv) > 1 and sys.argv[1] in ["--interactive", "-i"]:
        interactive_chat_session()
    else:
        # Default: run the full multi-turn demo verifying both read and write capabilities
        run_demo_multiturn()