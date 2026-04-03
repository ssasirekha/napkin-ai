import streamlit as st
import io
import base64
import json
import os
import requests
import math
from PIL import Image, ImageOps, ImageDraw, ImageFont, ImageColor
from openai import OpenAI

# --- 1. Cloud & App Configuration ---
st.set_page_config(page_title="Napkin AI Storyteller", page_icon="🎨", layout="wide")

st.markdown("""
    <style>
    .main-header { font-size: 2.2rem; font-weight: 800; color: #1e293b; margin-bottom: 1rem; }
    div.stButton > button:first-child[kind="primary"] {
        background-color: #3b82f6;
        border-color: #3b82f6;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Robust Font Loader (Prevents Freetype Errors) ---
def get_font(size):
    font_url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
    font_path = os.path.join(os.getcwd(), "Roboto-Bold.ttf")
    
    if not os.path.exists(font_path):
        try:
            r = requests.get(font_url, timeout=10)
            if r.status_code == 200:
                with open(font_path, "wb") as f:
                    f.write(r.content)
            else: return ImageFont.load_default()
        except: return ImageFont.load_default()
            
    try:
        return ImageFont.truetype(font_path, size)
    except:
        return ImageFont.load_default()

# --- 3. High-Precision AI Architect ---
def get_visual_logic(input_data, input_type="text"):
    if "OPENAI_API_KEY" not in st.secrets:
        st.error("Missing OPENAI_API_KEY in Secrets!")
        return None
        
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    system_prompt = """
    You are a Technical Business Strategist. Convert industrial data or screenshots into a visual narrative.
    Identify the specific 'Image Type' and 'Technical Name' first.
    Return ONLY a JSON object:
    {
        "type": "ProcessFlow",
        "title": "Specific Technical Name (e.g. SCADA Fleet Monitor)",
        "steps": ["Step 1 Description", "Step 2 Description", "Step 3 Description"],
        "summary": "Key business insight from this asset"
    }
    Types: 'ProcessFlow', 'KPIBox', or 'Comparison'.
    """
    
    try:
        if input_type == "image":
            base_img = base64.b64encode(input_data).decode("utf-8")
            content = [
                {"type": "text", "text": "Analyze this specific asset. Identify its type and create a visual story structure."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base_img}", "detail": "high"}}
            ]
        else:
            content = f"Turn this text into a business visual story: {input_data}"

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"AI Logic Error: {e}")
        return None

# --- 4. Napkin Rendering Engine ---
def draw_napkin_visual(logic):
    if not logic: return None
    
    width, height = 1200, 750
    img = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    f_title = get_font(48)
    f_step = get_font(26)
    f_desc = get_font(22)

    # Visual Branding
    draw.text((60, 50), logic.get("title", "ANALYSIS").upper(), fill="#0f172a", font=f_title)
    draw.rectangle([60, 115, 300, 123], fill="#3b82f6") # Blueprint blue accent

    if logic["type"] == "ProcessFlow":
        steps = logic.get("steps", [])
        for i, step in enumerate(steps[:4]):
            x = 60 + (i * 280)
            y = 260
            # Technical "Napkin" Box
            draw.rounded_rectangle([x, y, x+245, y+200], radius=15, fill="#f8fafc", outline="#3b82f6", width=3)
            
            # Simple text wrap
            words = step.split()
            txt_wrap = "\n".join([" ".join(words[i:i+2]) for i in range(0, len(words), 2)])
            draw.multiline_text((x+25, y+60), txt_wrap, fill="#1e293b", font=f_step, spacing=10)
            
            # Flow Arrow
            if i < len(steps) - 1 and i < 3:
                draw.line([x+255, y+100, x+275, y+100], fill="#94a3b8", width=4)

    elif logic["type"] == "KPIBox":
        steps = logic.get("steps", [])
        for i, kpi in enumerate(steps[:3]):
            x = 60 + (i * 370)
            draw.rounded_rectangle([x, 200, x+330, 450], radius=25, fill="#eff6ff", outline="#2563eb", width=2)
            draw.text((x+40, 280), kpi.upper(), fill="#1e40af", font=f_step)

    # Insight Summary Footer
    draw.rounded_rectangle([60, 620, 1140, 700], radius=10, fill="#f1f5f9")
    draw.text((80, 645), f"STRATEGIC INSIGHT: {logic.get('summary', '')}", fill="#475569", font=f_desc)
    
    return img

# --- 5. Main UI Interface ---
st.markdown('<p class="main-header">🎨 Napkin AI: Visual Storyteller</p>', unsafe_allow_html=True)

col_input, col_viz = st.columns([1, 2])

with col_input:
    st.subheader("📥 Data Source")
    mode = st.radio("Input Type", ["Analyze Industrial Screenshot", "Describe Process with Text"])
    
    data = None
    if mode == "Analyze Industrial Screenshot":
        file = st.file_uploader("Upload UI/Asset Image", type=['png', 'jpg', 'jpeg'])
        if file:
            data = file.getvalue()
            st.image(data, caption="Input Preview", use_container_width=True)
    else:
        data = st.text_area("Describe the workflow or metrics...", height=200, placeholder="e.g. The sensor reads temperature, sends it to the cloud gateway, and triggers a cooling fan if above 50C.")

    if st.button("🚀 GENERATE VISUAL STORY", type="primary", use_container_width=True):
        if data:
            with st.spinner("AI analyzing and architecting..."):
                st.session_state["napkin_logic"] = get_visual_logic(data, "image" if mode == "Analyze Industrial Screenshot" else "text")
        else:
            st.warning("Please provide an input first.")

with col_viz:
    st.subheader("🖼️ Resulting Visual")
    if "napkin_logic" in st.session_state and st.session_state["napkin_logic"]:
        logic = st.session_state["napkin_logic"]
        
        # Display identified type and name
        st.success(f"**Identified:** {logic.get('title')}")
        
        visual = draw_napkin_visual(logic)
        if visual:
            st.image(visual, use_container_width=True)
            
            # Download Logic
            buf = io.BytesIO()
            visual.save(buf, format="PNG")
            st.download_button("📥 Export for Presentation", buf.getvalue(), "napkin_story.png", "image/png", use_container_width=True)
    else:
        st.info("Upload an asset or describe a process to generate a Napkin-style visual story.")
