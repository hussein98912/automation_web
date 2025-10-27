import json
import os
from dotenv import load_dotenv
from openai import OpenAI

# تحميل المفتاح
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are a helpful AI assistant for an Automation Services company.
Use the company's Knowledge Base when possible to answer questions accurately.
Talk to customers in a friendly, professional way.
You can suggest workflow names and workflow details if the user asks.
"""

KNOWLEDGE_BASE_PATH = "Knlowagebase.json"
if os.path.exists(KNOWLEDGE_BASE_PATH):
    with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
        KNOWLEDGE_BASE = json.load(f)
else:
    KNOWLEDGE_BASE = {}

# ==============================
# 🔍 البحث في قاعدة المعرفة
# ==============================
def find_in_knowledge_base(user_message: str):
    msg = user_message.lower()
    kb = KNOWLEDGE_BASE

    if "hosting" in msg or "plan" in msg:
        return kb.get("hosting")
    if "real estate" in msg or "property" in msg:
        return kb.get("automation", {}).get("real_estate")
    if "ecommerce" in msg or "store" in msg:
        return kb.get("automation", {}).get("ecommerce")
    if "restaurant" in msg or "cafe" in msg:
        return kb.get("automation", {}).get("restaurants")
    if "hotel" in msg:
        return kb.get("automation", {}).get("hotels")
    if "camera" in msg or "surveillance" in msg:
        return kb.get("security", {}).get("cameras")
    if "access" in msg or "door" in msg:
        return kb.get("security", {}).get("access_control")

    for service in kb.get("services", []):
        if service["title"].lower() in msg or any(f.lower() in msg for f in service.get("features", [])):
            return service
    return None

# ==============================
# 💬 General AI Chat Response
# ==============================
def ai_chat_response(user_message, conversation_history=None):
    if conversation_history is None:
        conversation_history = []

    kb_info = find_in_knowledge_base(user_message)
    kb_text = ""
    if kb_info:
        kb_text = "Use this company info when replying:\n" + json.dumps(kb_info, indent=2)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for entry in conversation_history:
        messages.append({"role": "user", "content": entry.get("q", "")})
        messages.append({"role": "assistant", "content": entry.get("a", "")})
    
    messages.append({"role": "user", "content": f"{kb_text}\nCustomer: {user_message}"})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Sorry, I couldn’t process your request right now. ({str(e)})"

# ==============================
# 💡 Workflow Name Suggestions
# ==============================
def suggest_workflow_name(service: str, industry: str = None):
    prompt = (
        f"Suggest 3 short, catchy, professional workflow names for a {service} workflow"
    )
    if industry:
        prompt += f" that is suitable for the {industry} industry"
    
    prompt += ". Each name should be concise (max 5 words) and suitable for an automation project. "
    prompt += "Number them 1, 2, 3. Do not add extra text."

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content.strip()
        # Clean lines and remove extra intro
        ideas = [line.strip("•-0123456789. ").strip() 
                 for line in text.split("\n") 
                 if line.strip() and not line.lower().startswith(("here are","sure","reply"))]
        return ideas[:3] or ["SmartFlow", "AutoEase", "ProcessPro"]
    except Exception as e:
        return [f"Error generating names: {e}"]

# ==============================
# 🧩 Workflow Details Suggestions
# ==============================
def suggest_workflow_details(workflow_name: str, service: str = None, industry: str = None):
    # 🧠 Make the prompt more context-aware
    prompt = (
        f"Give exactly 3 short, creative workflow descriptions for a system called '{workflow_name}'. "
        "Each description should be 1–2 sentences describing its purpose and benefits. "
    )

    if service:
        prompt += f"The system is related to {service}. "
    if industry:
        prompt += f"It is designed for the {industry} industry. "

    prompt += "Number them 1, 2, 3. Do not include any introduction or extra text."

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.8,
        )
        text = response.choices[0].message.content.strip()

        # 🧹 Clean up and extract just the actual suggestions
        ideas = [
            line.strip("•-0123456789. ").strip()
            for line in text.split("\n")
            if line.strip() and not line.lower().startswith(("here are", "sure", "reply"))
        ]
        return ideas[:3]
    except Exception as e:
        return [f"Error generating details: {e}"]