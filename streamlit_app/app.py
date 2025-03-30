import streamlit as st
import google.generativeai as genai
import os
import time
from dotenv import load_dotenv
from google.api_core.exceptions import ResourceExhausted

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Initialize chat model
model = genai.GenerativeModel(model_name="models/gemini-1.5-pro-001")
chat = model.start_chat(history=[])

# Retry logic for rate limits
def send_message_with_retry(chat, user_input):
    try:
        return chat.send_message(user_input)
    except ResourceExhausted as e:
        st.warning("⚠️ Rate limit hit. Retrying in 45 seconds...")
        time.sleep(45)
        return chat.send_message(user_input)

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# App title
st.title("💬 SheCodesPrivate Career Chatbot")

# Display conversation
for role, text in st.session_state.chat_history:
    if role == "You":
        with st.chat_message("user"):
            st.markdown(text)
    else:
        with st.chat_message("assistant"):
            st.markdown(text)

# Chat input box
user_input = st.chat_input("Ask something about careers, skills, or goals...")

# Handle user message
if user_input:
    st.session_state.chat_history.append(("You", user_input))
    response = send_message_with_retry(chat, user_input)
    st.session_state.chat_history.append(("AI", response.text))

    # Extract career
    extract_prompt = (
        f"From this message, extract the final career the user wants to pursue: '{user_input}'. "
        "Only return the career title. If none is mentioned, respond with 'None'."
    )
    extract_model = genai.GenerativeModel("models/gemini-1.5-pro-001")
    extract_response = extract_model.generate_content(extract_prompt)
    chosen_career = extract_response.text.strip()

    if chosen_career and chosen_career.lower() not in ["", "none", "not mentioned"]:
        st.session_state.chosen_career = chosen_career

    st.rerun()  


# Show custom learning path if a career is selected
if "chosen_career" in st.session_state:
    st.markdown("---")
    career = st.session_state.chosen_career
    st.subheader(f"🎯 You're interested in becoming a **{career}**!")

    path_prompt = (
        f"Give me a beginner-friendly, practical learning path to become a {career}, "
        "including online resources like YouTube, Coursera, and tools to learn. "
        "Format it clearly and make it motivating for girls aged 12–19."
    )

    learning_path = model.generate_content(path_prompt)
    st.markdown("### 📚 Your Personalized Learning Path:")
    st.markdown(learning_path.text)

    st.download_button(
        label="📥 Download Your Learning Path",
        data=learning_path.text,
        file_name=f"{career}_learning_path.txt",
        mime="text/plain"
    )

# Unlock badge after 3 messages
user_msgs = [m for m in st.session_state.chat_history if m[0] == "You"]
if len(user_msgs) >= 3:
    st.success("🏅 Congrats! You've unlocked a 'Career Explorer' badge!")

# Download chat history
if st.button("📥 Download Chat History"):
    chat_log = "\n".join([f"{role}: {text}" for role, text in st.session_state.chat_history])
    st.download_button(
        label="Download Chat as .txt",
        data=chat_log,
        file_name="SheCodesPrivate_Chat.txt",
        mime="text/plain"
    )
