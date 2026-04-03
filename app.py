import streamlit as st
import io
import base64
import json
from PIL import Image, ImageDraw, ImageFont, ImageColor
from openai import OpenAI

# --- 1. Configuration & Style ---
st.set_page_config(page_title="Napkin Visual Studio", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .visual-card { border-radius: 15px; padding: 20px; background: white; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AI Visual Architect ---
def get_visual_logic(input_data, input_type="text"):
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    prompt = """
    You are a Business Visual Storyteller. Analyze the input and determine the best 'Napkin' visual.
    Choose one: 'ProcessFlow', 'Comparison', or 'KPIBox'.
    Return ONLY JSON:
    {
        "type": "ProcessFlow",
        "title": "Short Title",
        "steps": ["Step 1", "Step 2", "Step 3"],
        "summary": "One sentence insight"
    }
    """
    
    if input_type == "image":
        base_img = base64.b64encode(input_data).decode("utf-8")
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": [
                {"type": "text", "text": "Extract the business process or key metrics from this image."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base_img}"}}
            ]}
        ]
    else:
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Turn this into a visual story: {input_data}"}
        ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# --- 3. Dynamic Rendering Engine ---
def draw_napkin_visual(logic):
    # Create a high-res clean canvas
    width, height = 1200, 600
    img = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype("Roboto-Bold.ttf", 40)
        font_main = ImageFont.truetype("Roboto-Bold.ttf", 25)
    except:
        font_title = font_main = ImageFont.load_default()

    # Draw Title
    draw.text((50, 40), logic.get("title", "Insight").upper(), fill="#1e293b", font=font_title)
    draw.line((50, 100, 300, 100), fill="#3b82f6", width=5)

    if logic["type"] == "ProcessFlow":
        steps = logic.get("steps", [])
        for i, step in enumerate(steps):
            x = 50 + (i * 280)
            y = 250
            # Draw Step Box
            draw.rounded_rectangle([x, y, x+250, y+150], radius=15, fill="#eff6ff", outline="#3b82f6", width=3)
            # Draw Arrow
            if i < len(steps) - 1:
                draw.polygon([(x+255, y+75), (x+275, y+75), (x+265, y+85)], fill="#94a3b8")
            # Text
            draw.text((x+20, y+60), step[:20], fill="#1e3a8a", font=font_main)

    elif logic["type"] == "KPIBox":
        steps = logic.get("steps", ["Metric 1", "Metric 2"])
        for i, kpi in enumerate(steps[:3]):
            x = 50 + (i * 350)
            draw.rounded_rectangle([x, 200, x+300, y+400], radius=20, fill="#f8fafc", outline="#e2e8f0", width=2)
            draw.text((x+30, 280), kpi, fill="#3b82f6", font=font_title)

    return img

# --- 4. UI Layout ---
st.title("🎨 Napkin AI: Visual Business Storyteller")
st.subheader("Transform technical screenshots or text into clear visuals")

col_in, col_out = st.columns([1, 2])

with col_in:
    st.markdown("### 📥 Input Source")
    mode = st.radio("Choose Input", ["Technical Image", "Raw Text Description"])
    
    user_input = None
    if mode == "Technical Image":
        uploaded_file = st.file_uploader("Upload Industrial/UI Screenshot", type=['png', 'jpg'])
        if uploaded_file:
            st.image(uploaded_file, caption="Source Asset", use_container_width=True)
            user_input = uploaded_file.getvalue()
    else:
        user_input = st.text_area("Describe the business process or data...", placeholder="e.g. The water pump sends data to the SCADA system, which then alerts the engineer if pressure is high.")

    generate = st.button("🚀 Visualize Story", use_container_width=True, type="primary")

with col_out:
    st.markdown("### 🖼️ Generated Visual")
    if generate and user_input:
        with st.spinner("AI Architecting your story..."):
            input_type = "image" if mode == "Technical Image" else "text"
            visual_logic = get_visual_logic(user_input, input_type)
            
            # Show the logic found
            st.write(f"**Visual Type Identified:** {visual_logic['type']}")
            
            # Render and Show
            final_img = draw_napkin_visual(visual_logic)
            st.image(final_img, use_container_width=True)
            
            # Download
            buf = io.BytesIO()
            final_img.save(buf, format="PNG")
            st.download_button("📥 Export Visual", buf.getvalue(), file_name="napkin_visual.png")
    else:
        st.info("Awaiting input to generate visual story...")
