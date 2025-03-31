import streamlit as st
import google.generativeai as genai
import os
import time
import subprocess
from dotenv import load_dotenv
from google.api_core.exceptions import ResourceExhausted
from collections import deque
from PIL import Image, ImageEnhance
from datetime import datetime, timezone, timedelta


# --- Load Gemini API Key ---
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# --- Gemini model ---
model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-001")
chat = model.start_chat(history=[])

# --- In-memory cache for responses ---
response_cache = {}
cache_limit = 100

# --- Rate limiting variables ---
requests_this_hour = 0
last_request_time = None
hourly_request_limit = 50  # Replace with your free tier limit
rate_limit_reset_time = datetime.now(timezone.utc)

# --- Fallback responses ---
fallback_responses = {
    "default": "Sorry, I’m experiencing heavy traffic. Could you try again later?",
    "career_prompt": "I can’t suggest a career path right now. Please check back in a few minutes."
}

# Initialize session state variables
if "user_age" not in st.session_state:
    st.session_state.user_age = 0

# --- Retry and rate limit logic ---
def send_message(chat, user_input):
    global requests_this_hour, last_request_time, rate_limit_reset_time
    current_time = datetime.now(timezone.utc)

    # ✅ Ensure rate_limit_reset_time is timezone-aware
    if rate_limit_reset_time.tzinfo is None:
        rate_limit_reset_time = rate_limit_reset_time.replace(tzinfo=timezone.utc)

    # Reset hourly count if needed
    if current_time >= rate_limit_reset_time:
        requests_this_hour = 0
        rate_limit_reset_time = current_time + timedelta(hours=1)

    # Check if we're about to hit the rate limit
    if requests_this_hour >= hourly_request_limit:
        st.warning("⚠️ You’ve reached the maximum number of requests for this hour. Please wait until the next hour.")
        return fallback_responses["default"]

    # Make the API call
    try:
        response = chat.send_message(user_input)
        requests_this_hour += 1
        last_request_time = current_time
        return response
    except ResourceExhausted:
        for i in range(45, 0, -1):
            st.warning(f"⚠️ Rate limit hit. Retrying in {i} seconds...", icon="⏳")
            time.sleep(1)
        return fallback_responses["default"]

# --- Aleo age verifier (ZK Proof for Age ≥ 12) ---
def run_age_proof(age):
    try:
        result = subprocess.run(
            ["leo", "run", "verify_age", f"{age}u8"],
            capture_output=True,
            text=True,
            cwd="../aleo_contract"
        )
        return "• true" in result.stdout
    except Exception as e:
        st.error(f"Aleo age proof failed: {e}")
        return False

# --- Aleo badge check function ---
def run_aleo_badge_check(message_count: int) -> bool:
    try:
        result = subprocess.run(
            ["leo", "run", "prove_badges", f"{message_count}u8"],
            capture_output=True,
            text=True,
            cwd="../aleo_contract"  # Adjust if needed
        )
        return "• true" in result.stdout
    except Exception as e:
        st.error(f"Badge check failed: {e}")
        return False

# --- Session state init ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = deque(maxlen=cache_limit)
if "chosen_career" not in st.session_state:
    st.session_state.chosen_career = None
if "earned_badges" not in st.session_state:
    st.session_state.earned_badges = set()
if "badge_proofs" not in st.session_state:
    st.session_state.badge_proofs = {}

# --- Sidebar Navigation ---
st.sidebar.title("🔧 Navigation")
view = st.sidebar.radio("Go to:", ["💬 Chat", "🏅 Badge Dashboard", "🧰 My Badges"])

# --- Username & Age Verification with Retry Support (ZK Age Check) ---
with st.sidebar:
    st.header("🔐 Welcome!")

    # Clear if previously blocked for underage
    if st.session_state.get("underage_block", False):
        st.session_state.username = ""
        st.session_state.user_age = None

    st.session_state.username = st.text_input(
        "Choose a fun username (no real names)",
        max_chars=20,
        value=st.session_state.get("username", "")
    )

    # Masked age input (as password)
    raw_age = st.text_input("Enter your age", type="password")

    # Validate and store age
    if raw_age.isdigit():
        age = int(raw_age)
        if 10 <= age <= 100:
            st.session_state.user_age = age

            # --- ✅ Reset session data if username or age changed ---
            prev_username = st.session_state.get("prev_username")
            prev_age = st.session_state.get("prev_user_age")

            if (prev_username and st.session_state.username != prev_username) or \
            (prev_age and st.session_state.user_age != prev_age):
                st.session_state.chat_history = deque(maxlen=cache_limit)
                st.session_state.chosen_career = None
                st.session_state.earned_badges = set()
                st.session_state.badge_proofs = {}
                st.session_state.learning_path = None
                st.toast("🔄 New session started for new user or age!")

            # --- Store current values ---
            st.session_state.prev_username = st.session_state.username
            st.session_state.prev_user_age = st.session_state.user_age

        else:
            st.warning("🚫 Age must be between 10 and 100.")
            st.stop()
    elif raw_age != "":
        st.warning("🔢 Please enter a valid number for age.")
        st.stop()



# --- Block further app use if not passed age check ---
if st.session_state.username:
    if not run_age_proof(st.session_state.user_age):
        st.session_state.underage_block = True
        st.warning("🚫 This platform is for users aged 12 and above only.\nPlease enter a different age or username.")
        st.stop()
    else:
        st.session_state.underage_block = False
        st.success(f"✅ Welcome, {st.session_state.username}! You’ve been verified with zero-knowledge proof.")
else:
    st.stop()


# --- Track earned badges in session ---
if "earned_badges" not in st.session_state:
    st.session_state.earned_badges = set()

# --- "My Badges" Section ---
def show_my_badges():
    if st.session_state.earned_badges:
        st.markdown("---")
        st.markdown("## 🧰 My Badges")
        for badge in st.session_state.earned_badges:
            path = f"badges/{badge.lower().replace(' ', '_')}_badge.png"
            st.image(path, caption=badge, use_container_width=True)
            with open(path, "rb") as img:
                st.download_button(
                    label=f"📥 Download {badge} Badge",
                    data=img,
                    file_name=f"{badge.lower().replace(' ', '_')}_badge.png",
                    mime="image/png"
                )

# --- Aleo proof generator ---
def generate_aleo_proof(badge_name):
    if badge_name in st.session_state.badge_proofs:
        return True, st.session_state.badge_proofs[badge_name]
    
    try:
        badge_value = {
            "Career Explorer": 3,
            "Web Developer": 5,
            "Bug Squasher": 7,
            "Great Research": 10,
            "Skill Master": 12
        }.get(badge_name, 3)

        result = subprocess.run(
            ["leo", "run", "prove_badges", f"{badge_value}u8"],
            capture_output=True,
            text=True,
            cwd="../aleo_contract"
        )

        # Check if Leo verified successfully
        if "• true" in result.stdout:
            username = st.session_state.get("username", "UnknownUser")
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

            # Format a clean, readable proof
            clean_proof = (
                f"🔐 Aleo Badge Proof\n"
                f"👤 Username: {username}\n"
                f"🏅 Badge: {badge_name}\n"
                f"✅ Status: Verified by Aleo ZK Proof\n"
                f"🕒 Timestamp: {timestamp}"
            )

            # Store and return it
            st.session_state.badge_proofs[badge_name] = clean_proof
            return True, clean_proof
        else:
            return False, "⚠️ Aleo proof failed or badge condition not met."
    
    except Exception as e:
        return False, str(e)


# --- Badge dashboard ---
def badge_dashboard():
    st.markdown("---")
    st.markdown("## 🏅 Badge Dashboard")

    badges = {
        "Career Explorer": "badges/career_explorer_badge.png",
        "Web Developer": "badges/web_developer_badge.png",
        "Bug Squasher": "badges/bug_squasher_badge.png",
        "Great Research": "badges/great_research_badge.png",
        "Skill Master": "badges/skill_master_badge.png"
    }

    conditions = {
        "Career Explorer": lambda s: s.get("chosen_career") is not None,
        "Web Developer": lambda s: (s.get("chosen_career") or "").lower() == "web developer",
        "Bug Squasher": lambda s: any("bug" in m[1].lower() and "fix" in m[1].lower() for m in s.get("chat_history", [])),
        "Great Research": lambda s: sum(1 for m in s.get("chat_history", []) if m[0] == "You") >= 10,
        "Skill Master": lambda s: sum(1 for m in s.get("chat_history", []) if m[0] == "You" and "skill" in m[1].lower()) >= 3
    }

    st.write("Explore your progress below! 🔒 Locked badges will appear faded.")
    cols = st.columns(3)

    for i, (name, path) in enumerate(badges.items()):
        with cols[i % 3]:
            unlocked = conditions[name](st.session_state)

            if unlocked:
                if name not in st.session_state.earned_badges:
                    st.session_state.earned_badges.add(name)
                    st.toast(f"🎉 You've unlocked the **{name}** badge!")
                    st.balloons()

                st.image(path, caption=name, use_container_width=True)

                with open(path, "rb") as img:
                    st.download_button(
                        label=f"📥 Download {name} Badge",
                        data=img,
                        file_name=f"{name.lower().replace(' ', '_')}_badge.png",
                        mime="image/png"
                    )

                # Generate Aleo proof
                success, proof = generate_aleo_proof(name)
                if success:
                    st.download_button(
                        label=f"🔐 Download {name} Aleo Proof",
                        data=proof,
                        file_name=f"{name.lower().replace(' ', '_')}.proof",
                        mime="text/plain"
                    )
                else:
                    st.caption(f"⚠️ {proof}")
            else:
                img = Image.open(path).convert("LA")
                faded = ImageEnhance.Brightness(img).enhance(0.4)
                st.image(faded, caption=f"🔒 {name}", use_container_width=True)

# --- 💬 Chat View ---
if view == "💬 Chat":
# --- UI ---
    st.title("💬 SheCodesPrivate Career Chatbot")

    # --- Display chat history ---
    for role, text in st.session_state.chat_history:
        with st.chat_message("user" if role == "You" else "assistant"):
            st.markdown(text)

    # --- Chat input ---
    user_input = st.chat_input("Ask something about careers, skills, or goals...")

        # --- Handle input ---
    if user_input:
    # Check cache first
        if user_input in response_cache:
            response = response_cache[user_input]
        else:
            response = send_message(chat, user_input)
            response_cache[user_input] = response
            if len(response_cache) > cache_limit:
                response_cache.popitem(last=False)

        # ✅ Always extract response_text
        response_text = response.text.strip() if hasattr(response, "text") else str(response)

        st.session_state.chat_history.append(("You", user_input))
        st.session_state.chat_history.append(("AI", response_text))

        # ✅ Dynamic badge unlock logic
        badge_conditions = {
            "Career Explorer": st.session_state.chosen_career is not None,
            "Web Developer": st.session_state.chosen_career and st.session_state.chosen_career.lower() == "web developer",
            "Bug Squasher": any(isinstance(m[1], str) and "bug" in m[1].lower() and "fix" in m[1].lower()for m in st.session_state.chat_history),
            "Great Research": sum(1 for m in st.session_state.chat_history if m[0] == "You") >= 10,
            "Skill Master": sum(1 for m in st.session_state.chat_history if m[0] == "You" and "skill" in m[1].lower()) >= 3
        }

        for badge_name, condition in badge_conditions.items():
            if condition and badge_name not in st.session_state.earned_badges:
                st.session_state.earned_badges.add(badge_name)
                st.toast(f"🎉 You've unlocked the **{badge_name}** badge!")
                st.balloons()


        # --- Extract career title ---
        extract_prompt = (
            f"From this message, extract the final career the user wants to pursue: '{user_input}'. "
            "Only return the career title. If none is mentioned, respond with 'None'."
        )
        
        if requests_this_hour < hourly_request_limit:
            extract_response = model.generate_content(extract_prompt)
            requests_this_hour += 1
            chosen_career = extract_response.text.strip()
            if chosen_career and chosen_career.lower() not in ["", "none", "not mentioned"]:
                if chosen_career != st.session_state.get("chosen_career"):
                    st.session_state.chosen_career = chosen_career
                    st.session_state.learning_path = None  # Reset only if career has changed

        else:
            st.warning("⚠️ Request limit reached. Unable to extract career title.")

        st.rerun()

    # --- Learning path section ---
    if st.session_state.chosen_career:
        st.markdown("---")
        career = st.session_state.chosen_career
        st.subheader(f"🎯 You're interested in becoming a **{career}**!")

        path_prompt = (
            f"Give me a beginner-friendly, practical learning path to become a {career}, "
            "including online resources like YouTube, Coursera, and tools to learn. "
            "Format it clearly and make it motivating for girls aged 12–19."
        )

        if requests_this_hour < hourly_request_limit:
            learning_path = model.generate_content(path_prompt)
            requests_this_hour += 1
            st.markdown("### 📚 Your Personalized Learning Path:")
            st.markdown(learning_path.text)
        else:
            st.markdown(f"⚠️ I’ve hit my request limit. I can’t fetch a learning path for {career} right now.")

        st.download_button(
            label="📥 Download Your Learning Path",
            data=learning_path.text if requests_this_hour < hourly_request_limit else fallback_responses["career_prompt"],
            file_name=f"{career}_learning_path.txt",
            mime="text/plain"
        )



    # --- Download chat history ---
    if st.button("📥 Download Chat History"):
        chat_log = "\n".join([f"{role}: {text}" for role, text in st.session_state.chat_history])
        st.download_button(
            label="Download Chat as .txt",
            data=chat_log,
            file_name="SheCodesPrivate_Chat.txt",
            mime="text/plain"
        )

elif view == "🧰 My Badges":
    show_my_badges()
elif view == "🏅 Badge Dashboard":
    badge_dashboard()
