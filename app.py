import io
import json
import math
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# -----------------------------
# App configuration
# -----------------------------
st.set_page_config(
    page_title="Napkin AI Storyteller",
    page_icon="🎨",
    layout="wide",
)

st.markdown(
    """
    <style>
        .main-header {
            font-size: 2.2rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 0.25rem;
        }
        .sub-header {
            color: #475569;
            margin-bottom: 1rem;
        }
        .stTextArea textarea, .stTextInput input {
            border-radius: 12px;
        }
        div.stButton > button:first-child {
            background: linear-gradient(90deg, #2563eb, #1d4ed8);
            color: white;
            border: none;
            border-radius: 10px;
            font-weight: 600;
        }
        div.stDownloadButton > button:first-child {
            border-radius: 10px;
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Fonts
# -----------------------------
def get_font(size: int, bold: bool = False):
    """
    Load a font safely without downloading anything at runtime.
    Falls back to PIL default if a truetype font is not available.
    """
    candidates = []
    if bold:
        candidates.extend(
            [
                "DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/Library/Fonts/Arial Bold.ttf",
                "arialbd.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "DejaVuSans.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/Library/Fonts/Arial.ttf",
                "arial.ttf",
            ]
        )

    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            continue

    return ImageFont.load_default()


# -----------------------------
# OpenAI helper
# -----------------------------
def get_openai_client():
    api_key = None

    if "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
    elif "OPENAI_API_KEY" in st.session_state and st.session_state["OPENAI_API_KEY"]:
        api_key = st.session_state["OPENAI_API_KEY"]

    if not api_key:
        return None

    if OpenAI is None:
        return None

    return OpenAI(api_key=api_key)


# -----------------------------
# JSON handling
# -----------------------------
def safe_json_loads(raw_text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(raw_text)
    except Exception:
        pass

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw_text[start : end + 1])
        except Exception:
            return None
    return None


def normalize_logic(data: Dict[str, Any]) -> Dict[str, Any]:
    title = str(data.get("title", "Untitled Visual")).strip() or "Untitled Visual"
    chart_type = str(data.get("type", "Flow")).strip().title()
    if chart_type not in {"Flow", "Grid"}:
        chart_type = "Flow"

    nodes = data.get("nodes", [])
    if not isinstance(nodes, list):
        nodes = [str(nodes)]

    clean_nodes = []
    for node in nodes[:8]:
        text = str(node).strip()
        if text:
            clean_nodes.append(text)

    if not clean_nodes:
        clean_nodes = ["Input", "Process", "Outcome"]

    insight = str(data.get("insight", "")).strip()
    category = str(data.get("category", "General")).strip() or "General"

    return {
        "title": title,
        "type": chart_type,
        "category": category,
        "nodes": clean_nodes,
        "insight": insight,
    }


# -----------------------------
# Text measurement / wrapping
# -----------------------------
def text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text_by_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
) -> List[str]:
    words = text.split()
    if not words:
        return [""]

    lines = []
    current = words[0]

    for word in words[1:]:
        trial = f"{current} {word}"
        w, _ = text_size(draw, trial, font)
        if w <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def draw_multiline_centered(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    text: str,
    font,
    fill: str,
    line_spacing: int = 8,
):
    x1, y1, x2, y2 = box
    max_width = x2 - x1 - 30
    lines = wrap_text_by_width(draw, text, font, max_width)

    line_heights = [text_size(draw, line, font)[1] for line in lines]
    total_height = sum(line_heights) + max(0, len(lines) - 1) * line_spacing
    current_y = y1 + ((y2 - y1) - total_height) // 2

    for line, h in zip(lines, line_heights):
        w, _ = text_size(draw, line, font)
        current_x = x1 + ((x2 - x1) - w) // 2
        draw.text((current_x, current_y), line, font=font, fill=fill)
        current_y += h + line_spacing


# -----------------------------
# AI prompt building
# -----------------------------
def build_prompt_for_text(text: str) -> str:
    return f"""
You are a visual thinking assistant inspired by simple napkin-style concept diagrams.

Read the user's input and convert it into a compact visual plan.
Return ONLY valid JSON with this exact structure:

{{
  "title": "Short clear title",
  "type": "Flow or Grid",
  "category": "Optional broad category",
  "nodes": ["3 to 6 short node labels"],
  "insight": "One concise key takeaway"
}}

Rules:
- Keep the title under 8 words.
- Keep each node short, clear, and presentation-friendly.
- Use "Flow" when there is a sequence.
- Use "Grid" when there are categories or grouped ideas.
- Do not include markdown.
- Do not include explanation outside JSON.

User input:
{text}
""".strip()


def generate_napkin_logic(input_data: Any, input_type: str = "text") -> Optional[Dict[str, Any]]:
    client = get_openai_client()
    if client is None:
        st.error("OpenAI client is not available. Add OPENAI_API_KEY in Streamlit secrets or session state.")
        return None

    try:
        if input_type == "image":
            import base64

            encoded = base64.b64encode(input_data).decode("utf-8")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You convert screenshots or images into clean napkin-style visual summaries. "
                            "Return JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """
Analyze this image and convert it into a napkin-style visual structure.

Return ONLY valid JSON:
{
  "title": "Short clear title",
  "type": "Flow or Grid",
  "category": "Optional broad category",
  "nodes": ["3 to 6 short node labels"],
  "insight": "One concise key takeaway"
}
""".strip(),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{encoded}",
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
                temperature=0.3,
            )
        else:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": build_prompt_for_text(str(input_data))},
                ],
                temperature=0.3,
            )

        raw = response.choices[0].message.content
        data = safe_json_loads(raw)
        if not data:
            st.error("The AI response could not be parsed as JSON.")
            return None

        return normalize_logic(data)

    except Exception as exc:
        st.error(f"AI error: {exc}")
        return None


# -----------------------------
# Canvas creation
# -----------------------------
def create_canvas(width: int = 1400, height: int = 900):
    image = Image.new("RGB", (width, height), "#fcfcfd")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        [20, 20, width - 20, height - 20],
        radius=28,
        outline="#dbe4f0",
        width=3,
    )
    return image, draw


# -----------------------------
# Drawing sections
# -----------------------------
def draw_header(draw: ImageDraw.ImageDraw, logic: Dict[str, Any], width: int):
    title_font = get_font(44, bold=True)
    meta_font = get_font(20, bold=False)

    title = logic.get("title", "Untitled Visual")
    category = logic.get("category", "General")

    draw.text((70, 55), title, fill="#0f172a", font=title_font)
    draw.rounded_rectangle([70, 112, 300, 120], radius=4, fill="#2563eb")
    draw.text((70, 138), f"Category: {category}", fill="#64748b", font=meta_font)


def draw_footer(draw: ImageDraw.ImageDraw, logic: Dict[str, Any], width: int, height: int):
    insight = logic.get("insight", "").strip()
    if not insight:
        return

    footer_font = get_font(24, bold=False)
    x1, y1, x2, y2 = 70, height - 140, width - 70, height - 60
    draw.rounded_rectangle([x1, y1, x2, y2], radius=18, fill="#eff6ff", outline="#bfdbfe", width=2)
    lines = wrap_text_by_width(draw, f"Insight: {insight}", footer_font, (x2 - x1) - 30)

    current_y = y1 + 18
    for line in lines[:3]:
        draw.text((x1 + 20, current_y), line, fill="#1d4ed8", font=footer_font)
        current_y += 30


def draw_flow_layout(draw: ImageDraw.ImageDraw, nodes: List[str], width: int, height: int):
    node_font = get_font(26, bold=True)
    sub_font = get_font(18, bold=False)

    content_top = 240
    card_h = 220
    available_w = width - 140
    count = max(1, min(len(nodes), 5))
    gap = 24
    card_w = int((available_w - gap * (count - 1)) / count)
    card_w = max(180, min(card_w, 240))

    total_width = card_w * count + gap * (count - 1)
    start_x = (width - total_width) // 2
    y = content_top

    for i, node in enumerate(nodes[:count]):
        x1 = start_x + i * (card_w + gap)
        y1 = y
        x2 = x1 + card_w
        y2 = y1 + card_h

        draw.rounded_rectangle([x1, y1, x2, y2], radius=24, fill="#ffffff", outline="#2563eb", width=4)
        draw.rounded_rectangle([x1 + 16, y1 + 16, x1 + 90, y1 + 54], radius=14, fill="#dbeafe")
        draw.text((x1 + 36, y1 + 24), f"{i+1}", fill="#1d4ed8", font=sub_font)

        draw_multiline_centered(draw, (x1 + 10, y1 + 70, x2 - 10, y2 - 20), node, node_font, "#0f172a")

        if i < count - 1:
            arrow_y = y1 + card_h // 2
            start_arrow = x2 + 8
            end_arrow = x2 + gap - 8
            draw.line([start_arrow, arrow_y, end_arrow, arrow_y], fill="#94a3b8", width=5)
            draw.polygon(
                [
                    (end_arrow, arrow_y),
                    (end_arrow - 14, arrow_y - 8),
                    (end_arrow - 14, arrow_y + 8),
                ],
                fill="#94a3b8",
            )


def draw_grid_layout(draw: ImageDraw.ImageDraw, nodes: List[str], width: int, height: int):
    node_font = get_font(24, bold=True)

    items = nodes[:6]
    count = len(items)

    cols = 2 if count <= 4 else 3
    rows = math.ceil(count / cols)

    grid_top = 230
    grid_bottom = height - 180
    grid_left = 70
    grid_right = width - 70

    gap_x = 26
    gap_y = 26
    card_w = int((grid_right - grid_left - gap_x * (cols - 1)) / cols)
    card_h = int((grid_bottom - grid_top - gap_y * (rows - 1)) / rows)

    for idx, node in enumerate(items):
        r = idx // cols
        c = idx % cols
        x1 = grid_left + c * (card_w + gap_x)
        y1 = grid_top + r * (card_h + gap_y)
        x2 = x1 + card_w
        y2 = y1 + card_h

        draw.rounded_rectangle([x1, y1, x2, y2], radius=24, fill="#ffffff", outline="#60a5fa", width=3)
        draw_multiline_centered(draw, (x1 + 20, y1 + 20, x2 - 20, y2 - 20), node, node_font, "#0f172a")


def render_napkin(logic: Dict[str, Any]) -> Optional[Image.Image]:
    if not logic:
        return None

    width, height = 1400, 900
    image, draw = create_canvas(width, height)

    draw_header(draw, logic, width)

    nodes = logic.get("nodes", [])
    layout_type = logic.get("type", "Flow")

    if layout_type == "Grid":
        draw_grid_layout(draw, nodes, width, height)
    else:
        draw_flow_layout(draw, nodes, width, height)

    draw_footer(draw, logic, width, height)

    return image


# -----------------------------
# Session state
# -----------------------------
if "napkin_data" not in st.session_state:
    st.session_state["napkin_data"] = None

if "OPENAI_API_KEY" not in st.session_state:
    st.session_state["OPENAI_API_KEY"] = ""


# -----------------------------
# UI
# -----------------------------
st.markdown('<div class="main-header">🎨 Napkin AI Storyteller</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Turn text or screenshots into a clean napkin-style visual summary.</div>',
    unsafe_allow_html=True,
)

with st.expander("API key setup", expanded=False):
    st.text_input(
        "OpenAI API Key",
        type="password",
        key="OPENAI_API_KEY",
        help="If not present in Streamlit secrets, you can paste it here for this session.",
    )

left_col, right_col = st.columns([1.05, 1.45])

with left_col:
    st.subheader("Input")
    source = st.radio("Source", ["Text Description", "Screenshot Analysis"], horizontal=True)

    input_payload = None
    input_type = "text"

    if source == "Text Description":
        input_payload = st.text_area(
            "Describe the workflow, idea, or business logic",
            height=220,
            placeholder="Example: User uploads images, AI classifies them, groups them by category, creates an editable collage, and allows download.",
        )
        input_type = "text"
    else:
        uploaded = st.file_uploader("Upload an image or screenshot", type=["png", "jpg", "jpeg"])
        if uploaded is not None:
            input_payload = uploaded.getvalue()
            st.image(input_payload, caption="Uploaded screenshot", use_container_width=True)
        input_type = "image"

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Generate Visual", use_container_width=True):
            if not input_payload:
                st.warning("Please provide input first.")
            else:
                with st.spinner("Generating napkin logic..."):
                    st.session_state["napkin_data"] = generate_napkin_logic(input_payload, input_type=input_type)

    with c2:
        if st.button("Clear", use_container_width=True):
            st.session_state["napkin_data"] = None
            st.rerun()

    if st.session_state["napkin_data"]:
        st.markdown("---")
        st.subheader("Edit generated structure")

        data = st.session_state["napkin_data"]
        data["title"] = st.text_input("Title", value=data.get("title", ""))
        data["category"] = st.text_input("Category", value=data.get("category", "General"))
        data["type"] = st.selectbox("Layout", ["Flow", "Grid"], index=0 if data.get("type") == "Flow" else 1)
        data["insight"] = st.text_area("Insight", value=data.get("insight", ""), height=100)

        st.markdown("**Nodes**")
        nodes = data.get("nodes", [])
        edited_nodes = []
        for idx, node in enumerate(nodes):
            edited_nodes.append(st.text_input(f"Node {idx+1}", value=node, key=f"node_{idx}"))

        add_more = st.checkbox("Add one more node")
        if add_more and len(edited_nodes) < 8:
            edited_nodes.append(st.text_input("New node", value="", key="new_node"))

        data["nodes"] = [n.strip() for n in edited_nodes if n.strip()]
        st.session_state["napkin_data"] = data

with right_col:
    st.subheader("Visual Output")
    current = st.session_state["napkin_data"]

    if current:
        napkin_image = render_napkin(current)
        if napkin_image is not None:
            st.image(napkin_image, use_container_width=True)

            output = io.BytesIO()
            napkin_image.save(output, format="PNG")
            st.download_button(
                "Download PNG",
                data=output.getvalue(),
                file_name="napkin_ai_visual.png",
                mime="image/png",
                use_container_width=True,
            )

            st.markdown("#### Extracted JSON")
            st.json(current)
    else:
        st.info("Your napkin-style visual will appear here after generation.")
