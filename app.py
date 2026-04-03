import streamlit as st
import io
import base64
import json
import os
import requests
from PIL import Image, ImageDraw, ImageFont, ImageColor
from openai import OpenAI

# --- 1. Cloud Configuration ---
st.set_page_config(page_title="Napkin Visual AI", layout="wide")

# Function to safely get the font for Cloud environments
def get_font(size):
    font_url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
    font_path = "Roboto-Bold.ttf"
    if not os.path.exists(font_path):
        try:
            r = requests.get(font_url)
            with open(font_path, "wb") as f:
                f.write(r.content)
        except:
            return ImageFont.load_default()
    return ImageFont.truetype(font_path, size)

# --- 2. Hardened AI Architect ---
def get_visual_logic(input_data, input_type="text"):
    # Ensure key exists in Secrets
    if "OPENAI_API_KEY" not in st.secrets:
        st.error("Missing OPENAI_API_KEY in Streamlit Secrets!")
        return None
        
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    system_prompt = """
    You are a Business Visual Storyteller. Analyze the input and determine the best visual.
    Return ONLY a valid JSON object. Do not include markdown formatting or backticks.
    {
        "type": "ProcessFlow",
        "title": "Title of Visual",
        "steps": ["Step 1", "Step 2", "Step 3"],
        "summary": "Brief insight"
    }
    Types: 'ProcessFlow', 'KPIBox', or 'Comparison'.
    """
    
    try:
        if input_type == "image":
            base_img = base64.b64encode(input_data).decode("utf-8")
            content = [
                {"type": "text", "text": "Extract the core business logic from this image into a visual story structure."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base_img}", "detail": "high"}}
            ]
        else:
            content = f"Convert this text into a structured visual story: {input_data}"

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

# --- 3. Rendering Engine ---
def draw_napkin_visual(logic):
    if not logic: return None
    
    width, height = 1200, 700
    img = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    f_title = get_font(45)
    f_step = get_font(28)
    f_desc = get_font(20)

    # Header
    draw.text((60, 50), logic.get("title", "STRATEGY").upper(), fill="#1e293b", font=f_title)
    draw.rectangle([60, 110, 250, 118], fill="#3b82f6") # Accent bar

    if logic["type"] == "ProcessFlow":
        steps = logic.get("steps", [])
        for i, step in enumerate(steps[:4]): # Limit to 4 for layout
            x = 60 + (i * 280)
            y = 250
            # Box
            draw.rounded_rectangle([x, y, x+240, y+180], radius=20, fill="#f0f9ff", outline="#3b82f6", width=3)
            # Text wrapping (simple)
            words = step.split()
            line1 = " ".join(words[:2])
            line2 = " ".join(words[2:])
            draw.text((x+20, y+50), line1, fill="#1e3a8a", font=f_step)
            draw.text((x+20, y+90), line2, fill="#1e3a8a", font=f_step)
            
            if i < len(steps) - 1 and i < 3:
                draw.line([x+250, y+90, x+270, y+90], fill="#cbd5e1", width=4)

    # Footer Summary
    draw.text((60, 600), f"INSIGHT: {logic.get('summary', '')}", fill="#64748b", font=f_desc)
    
    return img

# --- 4. Streamlit App Interface ---
st.title("🎨 Napkin AI Storyteller")
st.write("Turn complex industrial data into visual business narratives.")

col_input, col_viz = st.columns([1, 2])

with col_input:
    mode = st.selectbox("Input Mode", ["Analyze Image", "Visualise Text"])
    data = None
    
    if mode == "Analyze Image":
        file = st.file_uploader("Upload Dashboard/Asset", type=['png', 'jpg', 'jpeg'])
        if file:
            data = file.getvalue()
            st.image(data, width=200)
    else:
        data = st.text_area("What's the story?", placeholder="Describe a workflow or data set...")

    if st.button("🚀 GENERATE VISUAL", type="primary", use_container_width=True):
        if data:
            st.session_state["napkin_logic"] = get_visual_logic(data, "image" if mode == "Analyze Image" else "text")
        else:
            st.warning("Please provide input first.")

with col_viz:
    if "napkin_logic" in st.session_state and st.session_state["napkin_logic"]:
        logic = st.session_state["napkin_logic"]
        with st.spinner("Rendering..."):
            visual = draw_napkin_visual(logic)
            if visual:
                st.image(visual, use_container_width=True)
                
                # Download Button
                buf = io.BytesIO()
                visual.save(buf, format="PNG")
                st.download_button("📥 Export for Slides", buf.getvalue(), "napkin_visual.png", "image/png")
    else:
        st.info("Your visual story will appear here once generated.")
