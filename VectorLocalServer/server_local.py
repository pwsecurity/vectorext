"""
Vector AI Local Server — Windows Edition
=========================================
Runs on localhost:5002. Extension connects here for chat/agent.
Authentication is validated against PythonAnywhere (once per run).

Usage: python server_local.py
"""

import os
import json
import logging
import threading
import time
import uuid
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from datetime import datetime, timedelta
import google.genai as genai
from google.genai import types
import requests as http_requests  # renamed to avoid conflict with flask.request

# ================= CONFIGURATION =================

REMOTE_API_BASE = "https://rupaahsan2d.pythonanywhere.com"
LOCAL_PORT = 5002
GENAI_HTTP_TIMEOUT_SEC = int(os.getenv("GENAI_HTTP_TIMEOUT_SEC", "90"))

DEFAULT_MODELS_CONFIG = [
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "priority": 1},
    {"id": "gemini-robotics-er-1.5-preview", "name": "Gemini Robotics ER", "priority": 2},
    {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite", "priority": 3},
    {"id": "gemini-flash-lite-latest", "name": "Gemini Flash Lite Latest", "priority": 4},
    {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash Preview", "priority": 5},
    {"id": "gemini-2.5-flash-preview-09-2025", "name": "Gemini 2.5 Flash Preview 09-2025", "priority": 6},
    {"id": "gemini-3.1-flash-lite-preview", "name": "Gemini 3.1 Flash Lite Preview", "priority": 7},
]

DEFAULT_PERSONA = {
    'name': 'Jake Fisher',
    'age': '40',
    'dob': 'November 23, 1985',
    'gender': 'Male',
    'ethnicity': 'White (Not Hispanic/Latino)',
    'job': 'IT Manager',
    'job_type': 'Full time (30+HR)',
    'occupation_area': 'Information and Technology / Software',
    'post': 'Higher Managerial / Director',
    'company_size': '500-999 employees',
    'company_revenue': '50M-100M',
    'income': '120,000 USD (Before Tax)',
    'assets': '5 Million USD (Investable)',
    'education': 'PhD / Doctorate',
    'house': 'Own (Single Family Home)',
    'decision_maker': 'Myself (All sections)',
    'pets': 'Cat & Dog',
    'address': '7 E 75th St',
    'city': 'New York',
    'state': 'New York',
    'zip': '10021',
    'marital_status': 'Married',
    'spouse_name': 'Sara',
    'spouse_age': '33',
    'children': '2',
    'child1': '14 year old boy James Fisher (18 Feb 2011)',
    'child2': '8 year old girl Sinthiya Fisher (07 Feb 2017)',
    'child_interest': 'Yes (Always)'
}

# ================= LOGGING =================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================= FLASK APP =================

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "*")
        response.headers.add('Access-Control-Allow-Methods', "*")
        return response

# ================= AUTH CACHE =================
# In-memory cache — lives only while server is running.
# When server stops (PC shutdown / window closed), cache is cleared.
# Next run, user logs in again → cache is rebuilt from PythonAnywhere.

_auth_cache = {}       # {email: {profile, persona, api_keys, system_settings, ...}}
_auth_lock = threading.Lock()

def get_cached_user(email):
    """Get cached user data. Returns None if not cached."""
    with _auth_lock:
        return _auth_cache.get(email)

def cache_user(email, data):
    """Store user data in cache."""
    with _auth_lock:
        _auth_cache[email] = data

def update_cache_field(email, field, value):
    """Update a single field in cached user data."""
    with _auth_lock:
        if email in _auth_cache:
            _auth_cache[email][field] = value

def validate_auth_local():
    """
    Validate auth from request body against local cache.
    Returns (is_valid, email, error_message).
    """
    try:
        if not request.is_json:
            try:
                data = request.get_json(force=True) or {}
            except Exception:
                data = {}
        else:
            data = request.json or {}
    except Exception as e:
        logger.error(f"Error parsing request JSON: {e}")
        return False, None, 'Invalid request format'

    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not email:
        return False, None, 'Email is required'
    if not password:
        return False, None, 'Password is required'

    cached = get_cached_user(email)
    if not cached:
        return False, None, 'Please login first. Your session has not been validated yet.'

    if cached.get('password') != password:
        return False, None, 'Invalid email or password'

    # Check status
    if cached.get('status') != 'approved':
        return False, None, f"Your account status is: {cached.get('status', 'unknown')}"

    # Check expiry
    expiry_str = cached.get('expiry_date')
    if expiry_str:
        try:
            expiry_date = datetime.fromisoformat(expiry_str)
            if datetime.now() > expiry_date:
                return False, None, 'Subscription expired.'
        except Exception:
            pass

    return True, email, None

# ================= REMOTE API HELPERS =================

def remote_login(email, password, device_id):
    """Call PythonAnywhere login API."""
    try:
        resp = http_requests.post(
            f"{REMOTE_API_BASE}/api/auth/login",
            json={"email": email, "password": password, "device_id": device_id},
            timeout=30
        )
        return resp.json(), resp.status_code
    except Exception as e:
        logger.error(f"Remote login error: {e}")
        return {"error": f"Cannot connect to authentication server: {e}"}, 503

def remote_get_profile(email, password, device_id):
    """Fetch full user profile from PythonAnywhere."""
    try:
        resp = http_requests.post(
            f"{REMOTE_API_BASE}/api/user/profile",
            json={"email": email, "password": password, "device_id": device_id},
            timeout=30
        )
        return resp.json(), resp.status_code
    except Exception as e:
        logger.error(f"Remote profile fetch error: {e}")
        return {"error": f"Cannot fetch user profile: {e}"}, 503

def remote_proxy(endpoint, body, timeout=30):
    """Proxy a request to PythonAnywhere."""
    try:
        resp = http_requests.post(
            f"{REMOTE_API_BASE}{endpoint}",
            json=body,
            timeout=timeout
        )
        return resp.json(), resp.status_code
    except Exception as e:
        logger.error(f"Remote proxy error for {endpoint}: {e}")
        return {"error": f"Cannot connect to remote server: {e}"}, 503

# ================= API KEY MANAGEMENT =================

class APIKeyManager:
    def __init__(self):
        self.lock = threading.Lock()

    def get_client(self, api_key):
        try:
            return genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=GENAI_HTTP_TIMEOUT_SEC)
            )
        except Exception:
            return genai.Client(api_key=api_key)

key_manager = APIKeyManager()

def get_keys_for_user(email):
    """Get API keys for user from cache."""
    cached = get_cached_user(email)
    if not cached:
        return []
    return cached.get('api_keys', [])

# ================= CHAT SESSIONS =================

chat_sessions = {}
message_counters = {}

# ================= PROMPT BUILDERS =================

def build_system_prompt(persona_data):
    if not persona_data:
        persona_data = DEFAULT_PERSONA

    current_date = datetime.now().strftime('%B %d, %Y')

    def get_f(key, fallback="N/A"):
        val = persona_data.get(key)
        if val is None:
            return DEFAULT_PERSONA.get(key, fallback)
        if str(val).strip() == "":
            return fallback
        return val

    fact_sheet = "TODAY'S DATE: " + current_date + "\n\nPERSONAL FACT SHEET (YOUR TRUE IDENTITY):\n"
    fact_sheet += f"- Name: {get_f('name')}\n"
    fact_sheet += f"- Age: {get_f('age')} (Verify with DOB)\n"
    fact_sheet += f"- Date of Birth: {get_f('dob')}\n"
    fact_sheet += f"- Gender: {get_f('gender', 'Male')}\n"
    fact_sheet += f"- Ethnicity: {get_f('ethnicity')}\n"
    fact_sheet += f"- Marital Status: {get_f('marital_status')}\n"

    spouse = get_f('spouse_name')
    if spouse != "N/A":
        fact_sheet += f"- Spouse: {spouse}, {get_f('spouse_age')} years old\n"

    num_children = get_f('children')
    if num_children != "N/A" and num_children != "0":
        fact_sheet += f"- Children count: {num_children}\n"
        c1 = get_f('child1')
        if c1 != "N/A":
            fact_sheet += f"  1. {c1}\n"
        c2 = get_f('child2')
        if c2 != "N/A":
            fact_sheet += f"  2. {c2}\n"

    fact_sheet += f"- Residence: {get_f('house')} in {get_f('city')}, {get_f('state')} {get_f('zip')}\n"
    fact_sheet += f"- Street Address: {get_f('address')}\n"
    fact_sheet += f"- Occupation: {get_f('job')} ({get_f('job_type')})\n"
    fact_sheet += f"- Occupation Area: {get_f('occupation_area')}\n"
    fact_sheet += f"- Position: {get_f('post')}\n"
    fact_sheet += f"- Company: {get_f('company_size')}, Revenue {get_f('company_revenue')}\n"
    fact_sheet += f"- Annual Income: {get_f('income')}\n"
    fact_sheet += f"- Assets: {get_f('assets')}\n"
    fact_sheet += f"- Education: {get_f('education')}\n"
    fact_sheet += f"- Decision Maker: {get_f('decision_maker')}\n"
    fact_sheet += f"- Pets: {get_f('pets')}\n"

    persona_text = fact_sheet + "\nCRITICAL PROTOCOL: You are the person described above. These are the ONLY facts about your life. If a detail is not in this fact sheet or marked as 'N/A', it DOES NOT EXIST. Use TODAY'S DATE for calculations. Never contradict these facts."

    behavioral_instructions = f"""
CORE PERSONALITY:
You respond like a real human who regularly takes surveys.
Tone: natural, friendly, calm, positive, and human-like.
You smoke socially, drink occasionally, and do some physical activity at least once a week.
You never refuse any question.
You never say "not interested," "not excited," "I don't know," or "I've never used this."
If uncertain, give a mild, plausible human guess.
You have cats and dogs.
ANSWER RULES:
• Open-ended questions: 1–2 sentences only, short, clear, positive, casual, and human.
• Multiple choice / option questions: select all relevant answers, provide concise explanations if needed.
• Never repeat the question in your answer.
• Responses must sound spontaneous, natural, and human-like.
• Never give impossible events (lightning strikes, shark attacks, inventions, etc.)

PLAUSIBLE EXPERIENCE RULE:
For any survey question asking about age, usage, first time doing something, or personal experience:
• Always provide a realistic and plausible answer, even if the persona has never done it.
• Never say "I've never used this" or "I have no experience."
• Give a believable age or short human response (e.g., "I first tried it around 24.")
• Keep these answers short and natural, aligning with normal human experiences.

SURVEY ANSWERING RULES:
* Select all answers that logically fit your persona.
* Do not skip relevant choices.
* For slogans or brand claims, answer accurately; if unsure, say: "I'm not completely sure, but it seems familiar."
* Never choose "N/A."
* Open-ended answers: 1–2 sentences max.
* Multiple choice answers: short but can include 1–2 small bullets or highlights if needed.

CONCERN LEVEL RULES:
* Crime, robbery, family safety → "Somewhat concerned" or "Very concerned."
* Minor risks (traffic, minor delays) → "Not that concerned."
* Neutral/general topics → "Somewhat concerned."
* Even if unrelated, respond naturally and positively.

STEALTH & ANTI-DETECTION:
• Randomize sentence patterns and word choices for each answer.
• Avoid robotic phrasing or survey template patterns.
• Never repeat identical sentence openings.
• Add mild human touches: small habits, preferences, relatable feelings.
• Keep answers concise, natural, and varied.

ANTI-PATTERN RULES:
• Never repeat exact phrases across answers.
• Avoid formulaic structure.
• Sound spontaneous and human-like.
• Open-ended questions: 1–2 sentences max.
• Multiple choice questions: concise, accurate, logical.

COMMUNICATION RULES:
• No hashtags, emojis, or asterisks.
• No long paragraphs.
• No introductions, disclaimers, or closing lines.
• No job-title introductions.
• Use line breaks when needed.
• Keep everything clean and human.

FORMATTING:
1. No * or ** or # characters.
2. Dates uppercase (NOVEMBER 4).
3. Empty line between date entries.
4. No citations.

SEARCH RULE:
Use Google Search only to verify real-world facts if needed.

FINAL MISSION:
• Keep all answers aligned with persona data.
• NO introductory text or commentary.
• Answer EVERY SINGLE question/row in any survey image or text perfectly without skipping anything.
• Always answer every question.
• Open-ended: 1–2 concise, positive, human-like sentences.
• Multiple choice: select all relevant answers with short highlights if needed.
• Always provide plausible experiences with realistic ages and usage.
• Vary phrasing and sentence structures to avoid detection.

STRICT ADHERENCE:
1. You are NOT an AI. You ARE {get_f('name')}.
2. Every detail above is YOUR REAL LIFE.
3. AGE & SCHOOLING: Use TODAY'S DATE and birth dates.
   - James (Feb 2011) is 14. US: 9th Grade. UK: Year 10.
   - Sinthiya (Feb 2017) is 8. US: 3rd Grade. UK: Year 4.
4. ABSENT DATA RULE: If a child is marked 'N/A' or missing from the Fact Sheet above, they DO NOT EXIST. Do not select any options for them in surveys.
5. SINGLE CHOICE RULE: If a survey asks about "your child" (singular) but you have multiple, prioritize the OLDEST.
5. FIRST PERSON ONLY: Never say "The persona says..." or "According to the details...". Say "I have", "My son is", "My daughter is".
6. SURVEY LOGIC: You have been taking surveys for years. You are consistent and never contradict yourself.
7. STAY IN CHARACTER AT ALL COSTS.

RESPONSE FORMATTING:
• If the user asks for a table, survey, or structured list, you MUST output valid HTML wrapped in a specific container.
• Use the following structure for tables:
<div class="structured-response">
  <table class="survey-table">
    <tr class="survey-header"><th>Header 1</th><th>Header 2</th></tr>
    <tr class="survey-row"><td class="survey-cell">Value 1</td><td class="survey-cell">Value 2</td></tr>
    <tr class="survey-row selected-option"><td class="survey-cell">Selected Value</td><td class="survey-cell">Value</td></tr>
  </table>
</div>
• For Matrix/Likert scales (e.g. Brand vs Familiarity), use columns for options and mark the specific CELL as selected:
<div class="structured-response">
  <table class="survey-table">
    <tr class="survey-header"><th>Brand</th><th>Very Familiar</th><th>Somewhat</th><th>Not at all</th></tr>
    <tr class="survey-row">
      <td class="survey-cell">ESPN</td>
      <td class="survey-cell selected-option"></td>
      <td class="survey-cell"></td>
      <td class="survey-cell"></td>
    </tr>
  </table>
</div>
• Use class "selected-option" on the <tr> (for single choice rows) or <td> (for matrix cells) that represents your choice.
• For multiple choice lists:
<div class="structured-response">
  <ul class="option-list">
    <li class="option-item">Option A</li>
    <li class="option-item selected">Option B (Your Choice)</li>
  </ul>
</div>
"""
    return persona_text + behavioral_instructions


def build_agent_prompt(persona_data, page_context):
    base_system = build_system_prompt(persona_data)

    agent_instructions = f"""
You are now in AUTO-PILOT mode.
Your goal is to complete the tasks on the current webpage: {page_context.get('url')} - "{page_context.get('title')}"

FULL WEBPAGE TEXT CONTENT:
{page_context.get('text', '')}

HTML SOURCE CODE (for structure understanding):
{page_context.get('htmlSource', '')[:50000]}

QUESTION LABELS AND HEADINGS:
{json.dumps(page_context.get('labels', []), indent=2)}

INTERACTIVE ELEMENTS (from entire page):
{json.dumps(page_context.get('elements'), indent=2)}

PAGE INFO:
- Total elements found: {page_context.get('totalElements', 0)}
- Page dimensions: {page_context.get('pageDimensions', {})}
- Text length: {page_context.get('totalTextLength', 0)} characters

MISSION:
1. Analyze the ENTIRE page (including testing sections, all questions from top to bottom) and identify which questions or tasks need to be completed based on your persona.
2. Complete ALL survey questions AND testing sections (like "Vector Stealth Mode Testing" or similar test areas).
3. For textareas and input fields in testing sections, fill them with appropriate test responses.
4. For each task, select the best interactive element from the list above.
5. Return a REQUIRED JSON array of actions in this EXACT format:
[
  {{"type": "click", "vectorId": "el_1"}},
  {{"type": "type", "vectorId": "el_2", "value": "text"}},
  {{"type": "select", "vectorId": "el_3", "value": "OptionValue"}},
  {{"type": "drag", "vectorId": "el_source", "targetVectorId": "el_target"}},
  {{"type": "click_coordinate", "x": 500, "y": 600}}
]

RULES:
- VISION: Use the screenshot to understand state. If an element isn't in the list but visible, use 'click_coordinate' with viewport $X/Y$.
- PRECISION TEST: For "EXACT CENTER", use 'click_coordinate' at exactly (rect.x + rect.width/2, rect.y + rect.height/2).
- MAPPING/DRAGGING: For "Integrated Definitions" or "Matching" tasks, ALWAYS use 'drag' from the term to its definition zone.
- NO SUBMISSION: NEVER click "Next", "Submit", "Finish", "Done", or "Continue". Stop after completing questions.
- TESTING SECTIONS: If you see testing sections (like "Vector Stealth Mode Testing", "Test 1", "Test 2", etc.), you MUST fill them out. Fill textareas with test responses, click test buttons, interact with test elements.
- COMPLETE EVERYTHING: Answer ALL questions and complete ALL interactive elements on the page, including testing/validation sections.
- RADIO BUTTONS: Only click a radio button if it's NOT already selected. Check the element's current state before clicking.
- CHECKBOXES: Include "checked": true/false in your action to specify desired state. Don't click if already in desired state.
- SELECT ELEMENTS: Use 'select' type with the exact value from the dropdown options.
- FULL PAGE: The page content includes ALL questions from top to bottom. Process them in order.
- HTML SOURCE: Use the HTML source code to understand the structure and relationships between elements.
- Be human-like and follow your persona. Answer questions as {persona_data.get('name', 'Jake Fisher') if persona_data else 'Jake Fisher'}.
- DO NOT return any text. ONLY the JSON array.
- If multiple children are mentioned and you must pick one, choose the OLDEST (James).
- Be human-like and consistent with your persona.
- DO NOT return any conversational text. Return ONLY the JSON array.
- If no actions are possible or needed, return an empty array [].
- Your name is Vector.
"""
    return base_system + agent_instructions


# ================= CONTENT GENERATION =================

def generate_content_with_retry(client_func, user_email=None, *args, **kwargs):
    """Try all user API keys until one works."""
    keys = get_keys_for_user(user_email) if user_email else []
    if not keys:
        raise Exception("No API keys available. Please add your API keys in the extension's 'Key' settings.")

    for key in keys:
        try:
            client = key_manager.get_client(api_key=key)
            return client_func(client, *args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            if any(x in error_str for x in ["429", "quota", "exhausted", "permission", "403", "expired", "invalid_argument"]):
                logger.warning(f"Rotate API key for {user_email or 'global'} due to: {e}")
                continue
            else:
                raise e
    raise Exception("All API keys exhausted. Please add more keys or try again later.")


# ================= ROUTES =================

@app.route('/')
def home():
    return "Vector Local Server is running! 🚀 (localhost:{})".format(LOCAL_PORT)


@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        'api_base_url': f'http://localhost:{LOCAL_PORT}',
        'status': 'active',
        'mode': 'local'
    })


# ================= AUTH ROUTES =================

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.json or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password')
        device_id = data.get('device_id')

        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400

        # --- Check if already cached (same-run re-login) ---
        cached = get_cached_user(email)
        if cached and cached.get('password') == password:
            logger.info(f"User {email} already validated this session. Using cache.")
            return jsonify({
                'success': True,
                'email': email,
                'status': cached.get('status', 'approved'),
                'role': cached.get('role', 'user'),
                'is_expired': cached.get('is_expired', False),
                'expiry_date': cached.get('expiry_date', ''),
                'device_changed': False,
                'active_devices': cached.get('active_devices', 1),
                'is_refer_code': False
            })

        # --- First login this session → call PythonAnywhere ---
        logger.info(f"First login for {email} this session. Validating with PythonAnywhere...")

        # Step 1: Login to PythonAnywhere
        login_data, login_status = remote_login(email, password, device_id)
        if login_status != 200 or not login_data.get('success'):
            return jsonify(login_data), login_status if login_status != 200 else 401

        # If it's a refer code login, just pass through
        if login_data.get('is_refer_code'):
            return jsonify(login_data)

        # Step 2: Fetch full user profile from PythonAnywhere
        profile_data, profile_status = remote_get_profile(email, password, device_id)

        profile = {}
        system_settings = {'models_config': DEFAULT_MODELS_CONFIG, 'models': {m["id"]: True for m in DEFAULT_MODELS_CONFIG}}

        if profile_status == 200 and profile_data.get('success'):
            profile = profile_data.get('profile', {})
            system_settings = profile_data.get('system_settings', system_settings)
        else:
            # Fallback: If /api/user/profile doesn't exist yet, try individual endpoints
            logger.warning("Profile endpoint not available, fetching individual data...")

            # Fetch persona
            persona_resp, _ = remote_proxy('/api/persona/get', {'email': email, 'password': password, 'device_id': device_id})
            if persona_resp.get('persona'):
                profile['persona'] = persona_resp['persona']

            # Fetch keys
            keys_resp, _ = remote_proxy('/api/keys/get', {'email': email, 'password': password, 'device_id': device_id})
            if keys_resp.get('api_keys'):
                profile['api_keys'] = keys_resp['api_keys']

        # Step 3: Cache everything
        cache_data = {
            'password': password,
            'email': email,
            'status': login_data.get('status', 'approved'),
            'role': login_data.get('role', 'user'),
            'is_expired': login_data.get('is_expired', False),
            'expiry_date': login_data.get('expiry_date', ''),
            'active_devices': login_data.get('active_devices', 1),
            'device_changed': login_data.get('device_changed', False),
            # From profile
            'persona': profile.get('persona', DEFAULT_PERSONA),
            'api_keys': profile.get('api_keys', []),
            'model_access': profile.get('model_access', {m["id"]: True for m in DEFAULT_MODELS_CONFIG}),
            'media_access': profile.get('media_access', {'images': True, 'files': True, 'audio': True}),
            'message_limit': profile.get('message_limit', False),
            'auto_pilot': profile.get('auto_pilot', False),
            'use_server_keys': profile.get('use_server_keys', True),
            'session_limit': profile.get('session_limit', 1),
            # System settings
            'system_settings': system_settings,
            # Timestamp
            'cached_at': datetime.now().isoformat()
        }
        cache_user(email, cache_data)
        logger.info(f"User {email} validated and cached. Keys: {len(cache_data['api_keys'])}, Models: {len(cache_data['model_access'])}")

        return jsonify({
            'success': True,
            'email': email,
            'status': cache_data['status'],
            'role': cache_data['role'],
            'is_expired': cache_data['is_expired'],
            'expiry_date': cache_data['expiry_date'],
            'device_changed': cache_data['device_changed'],
            'active_devices': cache_data['active_devices'],
            'is_refer_code': False
        })

    except Exception as e:
        import traceback
        logger.error(f"Error in login: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """Proxy signup directly to PythonAnywhere."""
    data = request.json or {}
    resp_data, status = remote_proxy('/api/auth/signup', data)
    return jsonify(resp_data), status


# ================= PERSONA ROUTES =================

@app.route('/api/persona/get', methods=['POST'])
def get_persona():
    try:
        is_valid, email, error_msg = validate_auth_local()
        if not is_valid:
            return jsonify({'error': error_msg or 'Unauthorized'}), 401

        cached = get_cached_user(email)
        persona = cached.get('persona', DEFAULT_PERSONA) if cached else DEFAULT_PERSONA
        return jsonify({'persona': persona})
    except Exception as e:
        logger.error(f"Error in get_persona: {e}")
        return jsonify({'error': 'Server error'}), 500


@app.route('/api/persona/update', methods=['POST'])
def update_persona():
    try:
        is_valid, email, error_msg = validate_auth_local()
        if not is_valid:
            return jsonify({'error': error_msg or 'Unauthorized'}), 401

        data = request.json or {}
        new_persona = data.get('persona')

        # Update remote (PythonAnywhere)
        cached = get_cached_user(email)
        device_id = data.get('device_id', '')
        proxy_body = {
            'email': email,
            'password': cached.get('password', ''),
            'device_id': device_id,
            'persona': new_persona
        }
        resp_data, status = remote_proxy('/api/persona/update', proxy_body)

        if status == 200 and resp_data.get('success'):
            # Update local cache too
            update_cache_field(email, 'persona', new_persona)

        return jsonify(resp_data), status
    except Exception as e:
        logger.error(f"Error in update_persona: {e}")
        return jsonify({'error': 'Server error'}), 500


# ================= KEYS ROUTES =================

@app.route('/api/keys/get', methods=['POST'])
def get_user_keys():
    try:
        is_valid, email, error_msg = validate_auth_local()
        if not is_valid:
            return jsonify({'error': error_msg or 'Unauthorized'}), 401

        cached = get_cached_user(email)
        keys = cached.get('api_keys', []) if cached else []
        return jsonify({'api_keys': keys})
    except Exception as e:
        logger.error(f"Error in get_user_keys: {e}")
        return jsonify({'error': 'Server error'}), 500


@app.route('/api/keys/update', methods=['POST'])
def update_user_keys():
    try:
        is_valid, email, error_msg = validate_auth_local()
        if not is_valid:
            return jsonify({'error': error_msg or 'Unauthorized'}), 401

        data = request.json or {}
        new_keys = data.get('api_keys', [])

        # Proxy to PythonAnywhere (it validates keys)
        cached = get_cached_user(email)
        device_id = data.get('device_id', '')
        proxy_body = {
            'email': email,
            'password': cached.get('password', ''),
            'device_id': device_id,
            'api_keys': new_keys
        }
        resp_data, status = remote_proxy('/api/keys/update', proxy_body)

        if status == 200 and resp_data.get('success'):
            # Re-fetch keys from server to get validated list
            keys_resp, _ = remote_proxy('/api/keys/get', {
                'email': email,
                'password': cached.get('password', ''),
                'device_id': device_id
            })
            if keys_resp.get('api_keys') is not None:
                update_cache_field(email, 'api_keys', keys_resp['api_keys'])

        return jsonify(resp_data), status
    except Exception as e:
        logger.error(f"Error in update_user_keys: {e}")
        return jsonify({'error': 'Server error'}), 500


# ================= CHAT ROUTE =================

@app.route('/api/extension/chat', methods=['POST'])
def extension_chat():
    try:
        is_valid, email, error_msg = validate_auth_local()
        if not is_valid:
            return jsonify({'error': error_msg or 'Authentication required'}), 401

        try:
            data = request.json or {}
        except Exception as e:
            logger.error(f"Error parsing request JSON in extension_chat: {e}")
            return jsonify({'error': 'Invalid request format'}), 400

        cached = get_cached_user(email)
        if not cached:
            return jsonify({'error': 'Please login first.'}), 401

        user_text = (data.get('text', '') or '').strip()
        page_content = (data.get('page_content', '') or '').strip()
        include_page_context = bool(data.get('include_page_context', False))
        chat_session_id = data.get('chat_session_id', data.get('session_id', 'default_session'))
        file_obj = data.get('file')

        # Check Media Access
        if file_obj:
            media_access = cached.get('media_access', {'images': True, 'audio': True, 'files': True})
            m_type = file_obj.get('mime_type', '')
            if m_type.startswith('image/') and not media_access.get('images'):
                return jsonify({'error': 'Image upload access denied.'}), 403
            if m_type.startswith('audio/') and not media_access.get('audio'):
                return jsonify({'error': 'Audio upload access denied.'}), 403
            if not m_type.startswith('image/') and not m_type.startswith('audio/') and not media_access.get('files'):
                return jsonify({'error': 'File upload access denied.'}), 403

        if not user_text and not file_obj:
            return jsonify({'error': 'No input provided'}), 400

        # Maintain session history
        session_key = f"{email}_{chat_session_id}"
        if session_key not in chat_sessions:
            chat_sessions[session_key] = {'history': [], 'metadata': []}

        session = chat_sessions[session_key]
        if 'metadata' not in session:
            session['metadata'] = []

        # Enforce Message Limit (5 per minute)
        if cached.get('message_limit', False):
            now = time.time()
            if email not in message_counters:
                message_counters[email] = {'count': 0, 'reset_time': now + 60}

            counter = message_counters[email]
            if now >= counter['reset_time']:
                counter['count'] = 0
                counter['reset_time'] = now + 60

            if counter['count'] >= 5:
                wait_time = int(counter['reset_time'] - now)
                return jsonify({
                    'error': f'Rate limit exceeded. Please wait {wait_time} seconds.',
                    'rate_limited': True,
                    'countdown': wait_time
                }), 429

            counter['count'] += 1

        page_context_text = ""
        if include_page_context and page_content and page_content != "N/A":
            page_context_text = page_content[:12000]

        if page_context_text:
            prompt_with_context = (
                "Context from the webpage I am currently viewing:\n"
                "--- CONTENT START ---\n"
                f"{page_context_text}\n"
                "--- CONTENT END ---\n\n"
                f"My Question: {user_text}"
            )
        else:
            prompt_with_context = user_text

        user_persona = cached.get('persona', DEFAULT_PERSONA)
        config = build_system_prompt(user_persona)

        # Model access check
        sys_settings = cached.get('system_settings', {})
        global_models = sys_settings.get('models', {})
        user_models = cached.get('model_access', {})
        dynamic_config = sys_settings.get('models_config', DEFAULT_MODELS_CONFIG)

        available_models = []
        for m in dynamic_config:
            if global_models.get(m["id"], True) and user_models.get(m["id"], True):
                available_models.append(m)

        if not available_models:
            return jsonify({'error': 'No models available for your account. Please contact admin.'}), 503

        def call_gemini(c, p, model_id, f_obj=None, original_text=""):
            parts = []
            if p:
                parts.append(p)
            if f_obj:
                import base64
                parts.append(types.Part.from_bytes(data=base64.b64decode(f_obj['data']), mime_type=f_obj['mime_type']))

            chat = c.chats.create(
                model=model_id,
                config=types.GenerateContentConfig(
                    system_instruction=config,
                    temperature=0.4,
                    max_output_tokens=1200
                ),
                history=session['history']
            )
            if len(parts) == 1 and isinstance(parts[0], str):
                resp = chat.send_message(parts[0])
            else:
                resp = chat.send_message(parts)

            user_parts = [types.Part(text=original_text or p)]
            if f_obj and len(parts) > 1 and not isinstance(parts[1], str):
                user_parts.append(parts[1])
            session['history'].append(types.Content(role="user", parts=user_parts))

            if resp.candidates and resp.candidates[0].content:
                session['history'].append(resp.candidates[0].content)

            if len(session['history']) > 24:
                session['history'] = session['history'][-24:]
            if len(session['metadata']) > 24:
                session['metadata'] = session['metadata'][-24:]
            return resp

        # Waterfall through available models
        response = None
        used_model = None
        for model in available_models:
            try:
                logger.info(
                    "Chat request: email=%s session=%s model=%s text_len=%s",
                    email, chat_session_id, model['id'], len(user_text)
                )
                response = generate_content_with_retry(
                    lambda c, p=prompt_with_context, m=model['id'], f=file_obj, ot=user_text: call_gemini(c, p, m, f, ot),
                    user_email=email
                )
                used_model = model['id']
                session['metadata'].append({"model": used_model})
                break
            except Exception as e:
                logger.error(f"Model {model['id']} failed: {e}")
                continue

        if not response:
            return jsonify({'error': 'All available models failed'}), 533

        return jsonify({
            'text': response.text,
            'model': used_model
        })

    except Exception as e:
        import traceback
        logger.error(f"Server Error in extension_chat: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


# ================= AGENT ROUTE =================

@app.route('/api/agent/task', methods=['POST'])
def agent_task():
    try:
        is_valid, email, error_msg = validate_auth_local()
        if not is_valid:
            return jsonify({'error': error_msg or 'Unauthorized'}), 401

        try:
            data = request.json or {}
        except Exception as e:
            logger.error(f"Error parsing request JSON in agent_task: {e}")
            return jsonify({'error': 'Invalid request format'}), 400

        page_context = data.get('context')
        screenshot_data = data.get('screenshot')

        if not isinstance(page_context, dict):
            return jsonify({'error': 'Invalid page context. Please refresh the page and try again.'}), 400
        if screenshot_data is not None and not isinstance(screenshot_data, str):
            return jsonify({'error': 'Invalid screenshot payload.'}), 400

        cached = get_cached_user(email)
        if not cached:
            return jsonify({'error': 'Please login first.'}), 401

        if not cached.get('auto_pilot', False):
            return jsonify({'error': 'Auto-Pilot access denied.'}), 403

        user_persona = cached.get('persona', DEFAULT_PERSONA)
        agent_system_prompt = build_agent_prompt(user_persona, page_context)

        # Model access check
        sys_settings = cached.get('system_settings', {})
        global_models = sys_settings.get('models', {})
        user_models = cached.get('model_access', {})
        dynamic_config = sys_settings.get('models_config', DEFAULT_MODELS_CONFIG)
        available_models = [m for m in dynamic_config if global_models.get(m["id"], True) and user_models.get(m["id"], True)]

        def generate():
            last_failure_reason = None
            keys = get_keys_for_user(email)
            if not keys:
                try:
                    yield f"data: {json.dumps({'status': 'error', 'message': 'No API keys available. Add keys in the extension settings.'})}\n\n"
                except OSError:
                    logger.warning("Client disconnected while streaming no-key error")
                return

            for model in available_models:
                for key_idx, key in enumerate(keys):
                    status_info = {
                        "status": "update",
                        "message": f"Trying {model['name']} | Key: {key_idx + 1}"
                    }
                    try:
                        yield f"data: {json.dumps(status_info)}\n\n"
                    except OSError:
                        return

                    try:
                        client = key_manager.get_client(api_key=key)
                        parts = ["Generate the JSON list of actions to complete the tasks on this page."]
                        if screenshot_data:
                            import base64
                            try:
                                header, encoded = screenshot_data.split(",", 1)
                                mime_type = header.split(":")[1].split(";")[0]
                                parts.append(types.Part.from_bytes(data=base64.b64decode(encoded), mime_type=mime_type))
                            except Exception:
                                raise ValueError('Screenshot payload is not a valid data URL.')

                        resp = client.models.generate_content(
                            model=model['id'],
                            config=types.GenerateContentConfig(
                                system_instruction=agent_system_prompt,
                                temperature=0.4,
                                top_p=0.8,
                                top_k=40,
                                response_mime_type="application/json"
                            ),
                            contents=parts
                        )

                        logger.info(f"Vector Output ({model['id']}): {resp.text}")

                        raw_text = (resp.text or '').strip()
                        if not raw_text:
                            raise ValueError('Model returned an empty action payload.')

                        try:
                            actions = json.loads(raw_text)
                        except Exception:
                            cleaned = raw_text.replace('```json', '').replace('```', '').strip()
                            actions = json.loads(cleaned)

                        if isinstance(actions, dict):
                            actions = [actions]
                        if not isinstance(actions, list):
                            raise ValueError('Model returned invalid action format.')

                        actions = [act for act in actions if isinstance(act, dict)]

                        # Filter out submission clicks
                        submission_keywords = ["next", "submit", "finish", "continue", "done"]
                        filtered_actions = []
                        page_elements = page_context.get('elements', [])
                        if not isinstance(page_elements, list):
                            page_elements = []
                        for act in actions:
                            is_submit = False
                            if act.get('type') == 'click' and 'vectorId' in act:
                                for el in page_elements:
                                    if not isinstance(el, dict):
                                        continue
                                    if el.get('vectorId') == act['vectorId']:
                                        if any(k in str(el.get('text', '')).lower() for k in submission_keywords):
                                            is_submit = True
                                            break
                            if not is_submit:
                                filtered_actions.append(act)

                        try:
                            yield f"data: {json.dumps({'status': 'success', 'actions': filtered_actions, 'model': model['name'], 'key_idx': key_idx + 1})}\n\n"
                        except OSError:
                            return
                        return

                    except Exception as e:
                        error_str = str(e).lower()
                        last_failure_reason = str(e)
                        logger.warning(f"Model {model['id']} attempt {key_idx+1} failed: {e}")

                        if any(x in error_str for x in ["429", "quota", "exhausted", "permission", "403", "expired", "invalid_argument"]):
                            continue
                        else:
                            break

            final_message = 'All models failed or all API keys exhausted.'
            if last_failure_reason:
                final_message = f"{final_message} Last error: {last_failure_reason[:220]}"
            try:
                yield f"data: {json.dumps({'status': 'error', 'message': final_message})}\n\n"
            except OSError:
                return

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        import traceback
        logger.error(f"Agent Task Error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


# ================= CHAT HISTORY ROUTES =================

@app.route('/api/chat/history', methods=['POST'])
def get_chat_history():
    try:
        is_valid, email, error_msg = validate_auth_local()
        if not is_valid:
            return jsonify({'error': error_msg or 'Unauthorized'}), 401

        data = request.json or {}
        chat_session_id = data.get('chat_session_id', data.get('session_id', 'default_session'))

        session_key = f"{email}_{chat_session_id}"
        session = chat_sessions.get(session_key, {'history': [], 'metadata': []})

        formatted_history = []
        metadata_idx = 0
        for item in session['history']:
            role = "ai" if item.role == "model" else "user"
            text = ""
            if hasattr(item, 'parts') and item.parts:
                text = item.parts[0].text

            info = None
            if role == "ai" and 'metadata' in session and metadata_idx < len(session['metadata']):
                meta = session['metadata'][metadata_idx]
                model_info = meta.get('model', 'Unknown')
                info = f"{model_info}"
                metadata_idx += 1

            formatted_history.append({"role": role, "text": text, "info": info})

        return jsonify({"history": formatted_history})
    except Exception as e:
        logger.error(f"Error in get_chat_history: {e}")
        return jsonify({'error': 'Server error'}), 500


@app.route('/api/chat/clear', methods=['POST'])
def clear_chat():
    try:
        is_valid, email, error_msg = validate_auth_local()
        if not is_valid:
            return jsonify({'error': error_msg or 'Unauthorized'}), 401

        data = request.json or {}
        chat_session_id = data.get('chat_session_id', data.get('session_id', 'default_session'))

        session_key = f"{email}_{chat_session_id}"
        if session_key in chat_sessions:
            chat_sessions[session_key] = {'history': [], 'metadata': []}

        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error in clear_chat: {e}")
        return jsonify({'error': 'Server error'}), 500


# ================= EXTENSION VERSION (PROXY) =================

@app.route('/api/extension/version', methods=['GET'])
def extension_version():
    """Proxy to PythonAnywhere for extension version info."""
    try:
        resp = http_requests.get(f"{REMOTE_API_BASE}/api/extension/version", timeout=10)
        return jsonify(resp.json())
    except Exception:
        return jsonify({'version': 'unknown', 'uploaded_at': ''})


# ================= MAIN =================

if __name__ == '__main__':
    from waitress import serve
    print("")
    print("  ========================================")
    print("    Vector AI Local Server")
    print("  ========================================")
    print(f"  Running on http://localhost:{LOCAL_PORT}")
    print("")
    print("  Extension will auto-detect this server.")
    print("  Keep this window open while using Vector.")
    print("  Close this window to stop the server.")
    print("  ========================================")
    print("")
    serve(app, host='127.0.0.1', port=LOCAL_PORT)
