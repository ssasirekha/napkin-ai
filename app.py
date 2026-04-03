import io
import json
import math
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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
            font-size: 2.3rem;
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
            background: linear-gradient(90deg, #7c3aed, #2563eb);
            color: white;
            border: none;
            border-radius: 10px;
            font-weight: 600;
        }
        div.stDownloadButton > button:first-child {
            border-radius: 10px;
            font-weight: 600;
            background: linear-gradient(90deg, #ec4899, #8b5cf6);
            color: white;
            border: none;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Fonts
# -----------------------------
def get_font(size: int, bold: bool = False):
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

    if not api_key or OpenAI is None:
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
# Text helpers
# -----------------------------
def text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text_by_width(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
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


def draw_multiline_centered(draw, box, text, font, fill, line_spacing=8):
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
# AI prompt
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
                        "content": "You convert screenshots into colorful napkin-style visual summaries. Return JSON only.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """
Analyze this image and convert it into a visual structure.

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
                temperature=0.4,
            )
        else:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": build_prompt_for_text(str(input_data))},
                ],
                temperature=0.4,
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
# Attractive color palette
# -----------------------------
PALETTE = [
    {"fill": "#FCE7F3", "border": "#EC4899", "text": "#9D174D"},
    {"fill": "#EDE9FE", "border": "#8B5CF6", "text": "#5B21B6"},
    {"fill": "#DBEAFE", "border": "#3B82F6", "text": "#1D4ED8"},
    {"fill": "#CCFBF1", "border": "#14B8A6", "text": "#0F766E"},
    {"fill": "#FEF3C7", "border": "#F59E0B", "text": "#B45309"},
    {"fill": "#DCFCE7", "border": "#22C55E", "text": "#15803D"},
    {"fill": "#FEE2E2", "border": "#EF4444", "text": "#B91C1C"},
    {"fill": "#E0F2FE", "border": "#0EA5E9", "text": "#0369A1"},
]


# -----------------------------
# Canvas and shapes
# -----------------------------
def create_gradient_background(width: int, height: int) -> Image.Image:
    bg = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(bg)

    # soft layered bands to simulate a modern presentation background
    draw.rounded_rectangle([20, 20, width - 20, height - 20], radius=32, fill="#fffdfd")
    draw.ellipse([-100, -60, 380, 280], fill="#fdf2f8")
    draw.ellipse([width - 420, -80, width + 40, 260], fill="#eef2ff")
    draw.ellipse([width - 350, height - 260, width + 80, height + 40], fill="#ecfeff")
    draw.ellipse([-160, height - 260, 320, height + 80], fill="#fef9c3")

    draw.rounded_rectangle(
        [22, 22, width - 22, height - 22],
        radius=30,
        outline="#e2e8f0",
        width=2,
    )
    return bg


def draw_shadowed_card(base_img, box, radius=28, shadow_offset=(10, 10), shadow_blur=12,
                       fill="#ffffff", border="#cbd5e1", border_width=3):
    x1, y1, x2, y2 = box

    shadow = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    sx1 = x1 + shadow_offset[0]
    sy1 = y1 + shadow_offset[1]
    sx2 = x2 + shadow_offset[0]
    sy2 = y2 + shadow_offset[1]

    shadow_draw.rounded_rectangle(
        [sx1, sy1, sx2, sy2],
        radius=radius,
        fill=(15, 23, 42, 55),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
    base_img.alpha_composite(shadow)

    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=border, width=border_width)
    base_img.alpha_composite(overlay)


# -----------------------------
# Rendering
# -----------------------------
def draw_header(draw, logic, width):
    title_font = get_font(48, bold=True)
    category_font = get_font(22, bold=True)
    subtitle_font = get_font(20, bold=False)

    title = logic.get("title", "Untitled Visual")
    category = logic.get("category", "General")

    draw.text((70, 52), title, fill="#0f172a", font=title_font)

    # multicolor accent
    draw.rounded_rectangle([70, 116, 180, 126], radius=5, fill="#ec4899")
    draw.rounded_rectangle([188, 116, 298, 126], radius=5, fill="#8b5cf6")
    draw.rounded_rectangle([306, 116, 416, 126], radius=5, fill="#3b82f6")

    # category pill
    pill_x1, pill_y1, pill_x2, pill_y2 = 70, 145, 250, 185
    draw.rounded_rectangle([pill_x1, pill_y1, pill_x2, pill_y2], radius=20, fill="#f8fafc", outline="#cbd5e1", width=2)
    draw.text((pill_x1 + 18, pill_y1 + 8), category, fill="#475569", font=category_font)

    draw.text((280, 152), "AI-generated visual summary", fill="#64748b", font=subtitle_font)


def draw_footer(draw, logic, width, height):
    insight = logic.get("insight", "").strip()
    if not insight:
        return

    title_font = get_font(22, bold=True)
    body_font = get_font(24, bold=False)

    x1, y1, x2, y2 = 70, height - 150, width - 70, height - 58
    draw.rounded_rectangle([x1, y1, x2, y2], radius=24, fill="#ffffff", outline="#cbd5e1", width=2)

    # left accent bar
    draw.rounded_rectangle([x1 + 12, y1 + 12, x1 + 28, y2 - 12], radius=8, fill="#8b5cf6")
    draw.text((x1 + 45, y1 + 16), "KEY INSIGHT", fill="#7c3aed", font=title_font)

    lines = wrap_text_by_width(draw, insight, body_font, (x2 - x1) - 90)
    current_y = y1 + 50
    for line in lines[:3]:
        draw.text((x1 + 45, current_y), line, fill="#334155", font=body_font)
        current_y += 32


def draw_flow_layout(base_img, draw, nodes, width, height):
    node_font = get_font(28, bold=True)
    num_font = get_font(20, bold=True)

    count = max(1, min(len(nodes), 5))
    top_y = 270
    card_h = 250
    gap = 24
    available_w = width - 150
    card_w = int((available_w - gap * (count - 1)) / count)
    card_w = max(190, min(card_w, 235))

    total_w = card_w * count + gap * (count - 1)
    start_x = (width - total_w) // 2

    for i in range(count):
        node = nodes[i]
        colors = PALETTE[i % len(PALETTE)]

        x1 = start_x + i * (card_w + gap)
        y1 = top_y
        x2 = x1 + card_w
        y2 = y1 + card_h

        draw_shadowed_card(
            base_img,
            [x1, y1, x2, y2],
            radius=30,
            fill=colors["fill"],
            border=colors["border"],
            border_width=4,
        )

        # step circle
        circle_r = 24
        cx = x1 + 34
        cy = y1 + 34
        draw.ellipse([cx - circle_r, cy - circle_r, cx + circle_r, cy + circle_r], fill=colors["border"])
        step_text = str(i + 1)
        tw, th = text_size(draw, step_text, num_font)
        draw.text((cx - tw // 2, cy - th // 2 - 1), step_text, fill="#ffffff", font=num_font)

        # mini label strip
        draw.rounded_rectangle([x1 + 70, y1 + 18, x2 - 18, y1 + 52], radius=14, fill="#ffffff")
        draw.text((x1 + 88, y1 + 24), "STEP", fill=colors["border"], font=num_font)

        draw_multiline_centered(
            draw,
            (x1 + 18, y1 + 74, x2 - 18, y2 - 25),
            node,
            node_font,
            colors["text"],
            line_spacing=10,
        )

        # connector
        if i < count - 1:
            next_colors = PALETTE[(i + 1) % len(PALETTE)]
            y_mid = y1 + card_h // 2
            x_start = x2 + 8
            x_end = x2 + gap - 8

            draw.line([x_start, y_mid, x_end, y_mid], fill=next_colors["border"], width=6)
            draw.polygon(
                [
                    (x_end, y_mid),
                    (x_end - 14, y_mid - 9),
                    (x_end - 14, y_mid + 9),
                ],
                fill=next_colors["border"],
            )


def draw_grid_layout(base_img, draw, nodes, width, height):
    node_font = get_font(26, bold=True)

    items = nodes[:6]
    count = len(items)

    cols = 2 if count <= 4 else 3
    rows = math.ceil(count / cols)

    grid_left = 70
    grid_right = width - 70
    grid_top = 240
    grid_bottom = height - 180

    gap_x = 24
    gap_y = 24

    card_w = int((grid_right - grid_left - gap_x * (cols - 1)) / cols)
    card_h = int((grid_bottom - grid_top - gap_y * (rows - 1)) / rows)

    for idx, node in enumerate(items):
        r = idx // cols
        c = idx % cols
        colors = PALETTE[idx % len(PALETTE)]

        x1 = grid_left + c * (card_w + gap_x)
        y1 = grid_top + r * (card_h + gap_y)
        x2 = x1 + card_w
        y2 = y1 + card_h

        draw_shadowed_card(
            base_img,
            [x1, y1, x2, y2],
            radius=28,
            fill=colors["fill"],
            border=colors["border"],
            border_width=4,
        )

        draw.rounded_rectangle([x1 + 18, y1 + 18, x1 + 150, y1 + 54], radius=14, fill="#ffffff")
        label = f"IDEA {idx+1}"
        draw.text((x1 + 34, y1 + 24), label, fill=colors["border"], font=get_font(18, bold=True))

        draw_multiline_centered(
            draw,
            (x1 + 20, y1 + 70, x2 - 20, y2 - 20),
            node,
            node_font,
            colors["text"],
            line_spacing=10,
        )


def render_napkin(logic: Dict[str, Any]) -> Optional[Image.Image]:
    if not logic:
        return None

    width, height = 1450, 920

    bg = create_gradient_background(width, height).convert("RGBA")
    draw = ImageDraw.Draw(bg)

    draw_header(draw, logic, width)

    nodes = logic.get("nodes", [])
    layout_type = logic.get("type", "Flow")

    if layout_type == "Grid":
        draw_grid_layout(bg, draw, nodes, width, height)
    else:
        draw_flow_layout(bg, draw, nodes, width, height)

    draw_footer(draw, logic, width, height)

    return bg.convert("RGB")


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
st.markdown('<div class="sub-header">Turn text or screenshots into a bold, colorful visual summary.</div>', unsafe_allow_html=True)

with st.expander("API key setup", expanded=False):
    st.text_input(
        "OpenAI API Key",
        type="password",
        key="OPENAI_API_KEY",
        help="Paste here if not stored in Streamlit secrets.",
    )

left_col, right_col = st.columns([1.05, 1.45])

with left_col:
    st.subheader("Input")
    source = st.radio("Source", ["Text Description", "Screenshot Analysis"], horizontal=True)

    input_payload = None
    input_type = "text"

    if source == "Text Description":
        input_payload = st.text_area(
            "Describe the workflow, idea, or concept",
            height=220,
            placeholder="Example: Upload images, classify them, group by category, create an attractive collage, edit labels, and download.",
        )
        input_type = "text"
    else:
        uploaded = st.file_uploader("Upload screenshot/image", type=["png", "jpg", "jpeg"])
        if uploaded is not None:
            input_payload = uploaded.getvalue()
            st.image(input_payload, caption="Uploaded image", use_container_width=True)
        input_type = "image"

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Generate Visual", use_container_width=True):
            if not input_payload:
                st.warning("Please provide input first.")
            else:
                with st.spinner("Generating colorful visual..."):
                    st.session_state["napkin_data"] = generate_napkin_logic(input_payload, input_type=input_type)

    with c2:
        if st.button("Clear", use_container_width=True):
            st.session_state["napkin_data"] = None
            st.rerun()

    if st.session_state["napkin_data"]:
        st.markdown("---")
        st.subheader("Edit visual content")

        data = st.session_state["napkin_data"]
        data["title"] = st.text_input("Title", value=data.get("title", ""))
        data["category"] = st.text_input("Category", value=data.get("category", "General"))
        data["type"] = st.selectbox("Layout", ["Flow", "Grid"], index=0 if data.get("type") == "Flow" else 1)
        data["insight"] = st.text_area("Insight", value=data.get("insight", ""), height=90)

        st.markdown("**Nodes**")
        edited_nodes = []
        for idx, node in enumerate(data.get("nodes", [])):
            edited_nodes.append(st.text_input(f"Node {idx+1}", value=node, key=f"node_{idx}"))

        if st.checkbox("Add one more node") and len(edited_nodes) < 8:
            edited_nodes.append(st.text_input("New node", value="", key="new_node"))

        data["nodes"] = [n.strip() for n in edited_nodes if n.strip()]
        st.session_state["napkin_data"] = data

with right_col:
    st.subheader("Visual Output")
    current = st.session_state["napkin_data"]

    if current:
        img = render_napkin(current)
        if img:
            st.image(img, use_container_width=True)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.download_button(
                "Download PNG",
                data=buf.getvalue(),
                file_name="napkin_colorful_visual.png",
                mime="image/png",
                use_container_width=True,
            )

            st.markdown("#### JSON Structure")
            st.json(current)
    else:
        st.info("Your colorful visual will appear here.")
