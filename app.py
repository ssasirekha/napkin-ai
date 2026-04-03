import streamlit as st
import io
import base64
import json
import os
import requests
from PIL import Image, ImageDraw, ImageFont, ImageColor
from openai import OpenAI

# --- 1. Cloud Configuration ---
st.set_page_config(page_title="Napkin AI Storyteller", page_icon="🎨", layout="wide")

# Custom CSS for the Napkin aesthetic
st.markdown("""
    <style>
    .main-header { font-size: 2.2rem; font-weight: 800; color: #1e293b; }
    .stTextArea textarea { border-radius: 10px; border: 1px solid #3b82f6; }
    div.stButton > button:first-child { background-color: #3b82f6; color: white; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Robust Font Loader ---
def get_font(size):
    font_url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
    font_path = os.path.join(os.getcwd(), "Roboto-Bold.ttf")
    
    if not os.path.exists(font_path):
        try:
            r = requests.get(font_url, timeout=10)
            if r.status_code == 200:
                with open(font_path, "wb") as f: f.write(r.content)
            else: return ImageFont.load_default()
        except: return ImageFont.load_default()
            
    try: return ImageFont.truetype(font_path, size)
    except: return ImageFont.load_default()

# --- 3. AI Visual Architect ---
def generate_napkin_logic(input_data, input_type="text"):
    if "OPENAI_API_KEY" not in st.secrets:
        st.error("Please add OPENAI_API_KEY to Streamlit Secrets.")
        return None
        
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    system_prompt = """
    You are a Visual Business Consultant. Your goal is to simplify complex info into a 'Napkin Sketch'.
    Analyze the input and return ONLY a JSON object:
    {
        "title": "Clear Technical Title",
        "type": "Flow", 
        "nodes": ["Step A", "Step B", "Step C"],
        "insight": "The core strategic takeaway"
    }
    'type' can be 'Flow' (sequence) or 'Grid' (categories).
    """
    
    try:
        if input_type == "image":
            base_img = base64.b64encode(input_data).decode("utf-8")
            prompt_content = [
                {"type": "text", "text": "Extract the business logic from this asset and turn it into a visual story."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base_img}", "detail": "high"}}
            ]
        else:
            prompt_content = f"Turn this into a visual story: {input_data}"

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt_content}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"AI Error: {e}")
        return None

# --- 4. Napkin Rendering Engine ---
def render_napkin(logic):
    if not logic: return None
    
    width, height = 1200, 800
    canvas = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(canvas)
    
    f_title = get_font(50)
    f_body = get_font(28)
    f_small = get_font(22)

    # Header
    draw.text((80, 60), logic.get("title", "STRATEGY").upper(), fill="#1e293b", font=f_title)
    draw.rectangle([80, 130, 350, 138], fill="#3b82f6") # Napkin underline

    # Render Flow or Grid
    nodes = logic.get("nodes", [])
    for i, node in enumerate(nodes[:4]):
        x = 80 + (i * 270)
        y = 300
        # Draw "Sketch" Box
        draw.rounded_rectangle([x, y, x+230, y+220], radius=20, outline="#3b82f6", width=4)
        
        # Text Wrap
        words = node.split()
        line1 = " ".join(words[:2])
        line2 = " ".join(words[2:])
        draw.text((x+25, y+70), line1, fill="#1e3a8a", font=f_body)
        draw.text((x+25, y+110), line2, fill="#1e3a8a", font=f_body)
        
        # Connectors
        if i < len(nodes) - 1 and i < 3:
            draw.line([x+240, y+110, x+260, y+110], fill="#cbd5e1", width=3)

    # Insight Footer
    draw.rounded_rectangle([80, 650, 1120, 730], radius=15, fill="#eff6ff")
    draw.text((110, 675), f"💡 INSIGHT: {logic.get('insight', '')}", fill="#1d4ed8", font=f_small)
    
    return canvas

# --- 5. Streamlit UI ---
st.markdown('<p class="main-header">🎨 Napkin AI: Visual Storyteller</p>', unsafe_allow_html=True)

col_in, col_out = st.columns([1, 2])

with col_in:
    st.subheader("📥 Input")
    source = st.selectbox("How to feed the AI?", ["Screenshot Analysis", "Text Description"])
    
    data = None
    if source == "Screenshot Analysis":
        file = st.file_uploader("Upload Industrial Asset", type=['png', 'jpg'])
        if file:
            data = file.getvalue()
            st.image(data, width=250)
    else:
        data = st.text_area("Describe the workflow...", height=150)

    if st.button("🚀 VISUALIZE STORY", use_container_width=True):
        if data:
            with st.spinner("AI is sketching..."):
                st.session_state["napkin_data"] = generate_napkin_logic(data, "image" if source == "Screenshot Analysis" else "text")
        else:
            st.warning("Please provide input.")

with col_out:
    st.subheader("🖼️ The Visual Story")
    if "napkin_data" in st.session_state:
        res = render_napkin(st.session_state["napkin_data"])
        if res:
            st.image(res, use_container_width=True)
            
            # Download
            buf = io.BytesIO()
            res.save(buf, format="PNG")
            st.download_button("📥 Download Napkin Sketch", buf.getvalue(), "napkin_story.png", "image/png")
    else:
        st.info("Your visual business story will appear here.")
