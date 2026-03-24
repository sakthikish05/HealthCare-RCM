from flask import Flask, jsonify, request, make_response
from faker import Faker
import uuid
import random
import time
import os

app = Flask(__name__)
fake = Faker()

# ---------------------------
# CONFIG
# ---------------------------
PAGE_SIZE = 5
RATE_LIMIT = 20  # requests per minute
request_counts = {}

VALID_TOKEN = "mock_access_token_123"

# ---------------------------
# RATE LIMIT
# ---------------------------
def check_rate_limit(ip):
    current_minute = int(time.time() / 60)

    if ip not in request_counts:
        request_counts[ip] = {}

    if current_minute not in request_counts[ip]:
        request_counts[ip][current_minute] = 0

    request_counts[ip][current_minute] += 1

    return request_counts[ip][current_minute] <= RATE_LIMIT

# ---------------------------
# AUTH
# ---------------------------
def validate_token(req):
    auth = req.headers.get("Authorization", "")
    return auth == f"Bearer {VALID_TOKEN}"

@app.route("/auth/token", methods=["POST"])
def token():
    return jsonify({
        "access_token": VALID_TOKEN,
        "token_type": "Bearer",
        "expires_in": 3600
    })

# ---------------------------
# GENERATORS
# ---------------------------
def generate_patient():
    return {
        "resourceType": "Patient",
        "id": str(uuid.uuid4()),
        "name": [{
            "given": [fake.first_name()],
            "family": fake.last_name()
        }],
        "gender": random.choice(["male", "female"]),
        "birthDate": fake.date_of_birth().isoformat()
    }

def generate_encounter(pid):
    return {
        "resourceType": "Encounter",
        "id": str(uuid.uuid4()),
        "status": "finished",
        "subject": {"reference": f"Patient/{pid}"}
    }

def generate_observation(pid):
    return {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "status": "final",
        "subject": {"reference": f"Patient/{pid}"},
        "valueQuantity": {
            "value": random.randint(60, 180),
            "unit": "mmHg"
        }
    }

def generate_appointment(pid):
    return {
        "resourceType": "Appointment",
        "id": str(uuid.uuid4()),
        "status": "booked",
        "participant": [{
            "actor": {"reference": f"Patient/{pid}"}
        }]
    }

def generate_billing(pid):
    return {
        "resourceType": "Account",
        "id": str(uuid.uuid4()),
        "status": "active",
        "subject": [{"reference": f"Patient/{pid}"}],
        "balance": {
            "value": random.randint(500, 5000),
            "currency": "INR"
        }
    }

def generate_claim(pid):
    return {
        "resourceType": "Claim",
        "id": str(uuid.uuid4()),
        "status": "active",
        "patient": {"reference": f"Patient/{pid}"},
        "total": {
            "value": random.randint(1000, 10000),
            "currency": "INR"
        }
    }

# ---------------------------
# RESOURCE ROUTER
# ---------------------------
def generate_resource(resource_type, patient):
    pid = patient["id"]

    if resource_type == "Patient":
        return patient
    elif resource_type == "Encounter":
        return generate_encounter(pid)
    elif resource_type == "Observation":
        return generate_observation(pid)
    elif resource_type == "Appointment":
        return generate_appointment(pid)
    elif resource_type == "Account":
        return generate_billing(pid)
    elif resource_type == "Claim":
        return generate_claim(pid)
    else:
        return patient

# ---------------------------
# BUNDLE
# ---------------------------
def generate_bundle(resource_type, page, base_url):
    entries = []

    for _ in range(PAGE_SIZE):
        patient = generate_patient()
        resource = generate_resource(resource_type, patient)

        entries.append({
            "fullUrl": f"{base_url}/{resource_type}/{resource['id']}",
            "resource": resource
        })

    next_page = page + 1

    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1000,
        "entry": entries,
        "link": [
            {
                "relation": "self",
                "url": f"{base_url}/{resource_type}?page={page}"
            },
            {
                "relation": "next",
                "url": f"{base_url}/{resource_type}?page={next_page}"
            }
        ]
    }

# ---------------------------
# MAIN ENDPOINT
# ---------------------------
@app.route("/<resource_type>", methods=["GET"])
def get_resource_api(resource_type):

    # Rate limit
    ip = request.remote_addr
    if not check_rate_limit(ip):
        return make_response(jsonify({
            "error": "Rate limit exceeded"
        }), 429)

    # Auth
    if not validate_token(request):
        return make_response(jsonify({
            "error": "Unauthorized"
        }), 401)

    # Pagination
    page = int(request.args.get("page", 1))

    base_url = request.host_url.strip("/")
    bundle = generate_bundle(resource_type, page, base_url)

    return jsonify(bundle)

# ---------------------------
# HEALTH CHECK
# ---------------------------
@app.route("/")
def home():
    return "FHIR API Simulator Running"

# ---------------------------
# RUN
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)