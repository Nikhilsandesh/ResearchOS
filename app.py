
import os
import io
import re
import sqlite3
from datetime import datetime
from xml.sax.saxutils import escape

import streamlit as st
from dotenv import load_dotenv
from google import genai
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


# =====================================================
# 1. APPLICATION CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="ResearchOS | AI Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv()

MODEL_NAME = "gemini-3.8-flash"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "researchos.db")


# =====================================================
# 2. API KEY CONFIGURATION
# Streamlit Cloud Secrets + local .env
# =====================================================

def get_api_key():
    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "")
        if secret_key:
            return secret_key
    except Exception:
        pass

    return os.getenv("GEMINI_API_KEY", "")


API_KEY = get_api_key()


# =====================================================
# 3. GEMINI CLIENT
# =====================================================

@st.cache_resource
def get_gemini_client(api_key):
    if not api_key:
        return None

    return genai.Client(api_key=api_key)


client = get_gemini_client(API_KEY)


# =====================================================
# 4. DATABASE
# =====================================================

def init_database():

    with sqlite3.connect(DB_PATH) as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                report TEXT NOT NULL,
                sources TEXT,
                created_at TEXT NOT NULL
            )
        """)

        connection.commit()


def save_report(topic, report, sources, created_at):

    with sqlite3.connect(DB_PATH) as connection:

        connection.execute("""
            INSERT INTO reports
            (topic, report, sources, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            topic,
            report,
            "\n".join(sources),
            created_at
        ))

        connection.commit()


def get_reports():

    with sqlite3.connect(DB_PATH) as connection:

        connection.row_factory = sqlite3.Row

        rows = connection.execute("""
            SELECT *
            FROM reports
            ORDER BY id DESC
        """).fetchall()

    return [dict(row) for row in rows]


def delete_report(report_id):

    with sqlite3.connect(DB_PATH) as connection:

        connection.execute(
            "DELETE FROM reports WHERE id = ?",
            (report_id,)
        )

        connection.commit()


init_database()


# =====================================================
# 5. GEMINI RESEARCH ENGINE
# =====================================================

def generate_research(topic, depth, style):

    if client is None:
        raise RuntimeError(
            "Gemini API key is missing. "
            "Configure GEMINI_API_KEY in Streamlit Secrets."
        )

    depth_instructions = {
        "Quick Overview": (
            "Provide a concise overview with the most "
            "important concepts and examples."
        ),
        "Standard Research": (
            "Provide a detailed explanation with relevant "
            "examples, analysis and practical applications."
        ),
        "Deep Research": (
            "Provide an extensive, technically detailed "
            "analysis with comprehensive explanations, "
            "comparisons and limitations."
        )
    }

    style_instructions = {
        "Professional Academic": (
            "Use formal academic language and a structured "
            "professional writing style."
        ),
        "Beginner Friendly": (
            "Use simple English, clear explanations and "
            "easy-to-understand examples."
        ),
        "Technical": (
            "Use technical terminology, architecture details "
            "and implementation-oriented explanations."
        ),
        "Executive Summary": (
            "Focus on key findings, implications and "
            "actionable insights."
        )
    }

    prompt = f"""
You are ResearchOS, an intelligent AI research assistant.

Research topic:
{topic}

Research depth:
{depth}

Research style:
{style}

Depth instructions:
{depth_instructions[depth]}

Writing instructions:
{style_instructions[style]}

Create a structured research report containing:

1. Executive Summary
2. Introduction
3. Background and Context
4. Important Concepts
5. Detailed Analysis
6. Current Developments
7. Benefits and Opportunities
8. Challenges and Limitations
9. Future Scope
10. Conclusion

Additional instructions:

- Use Markdown headings.
- Explain concepts clearly.
- Include useful examples where appropriate.
- Avoid unsupported statistics.
- Do not invent references, citations or URLs.
- Do not claim to have performed live web searches.
- Clearly identify information that may require
  independent verification.
- Make the report relevant to the selected topic.
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty response. Please try again."
        )

    return response.text, []


# =====================================================
# 6. ERROR HANDLING
# =====================================================

def show_ai_error(error):

    message = str(error)
    message_lower = message.lower()

    if "503" in message or "unavailable" in message_lower:

        st.error(
            "Gemini is temporarily experiencing high demand. "
            "Please wait a few minutes and try again."
        )

    elif "429" in message or "resource_exhausted" in message_lower:

        st.error(
            "Gemini API quota or rate limit reached. "
            "Check your Google AI Studio project quota "
            "and try again after it resets."
        )

    elif "401" in message or "403" in message:

        st.error(
            "Gemini API authentication failed. "
            "Check your API key and project access."
        )

    else:

        st.error(f"Research generation failed: {message}")


# =====================================================
# 7. PDF GENERATOR
# =====================================================

def create_pdf(topic, report, created_at):

    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ResearchTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=28,
        textColor=colors.HexColor("#2447A5"),
        alignment=TA_CENTER,
        spaceAfter=18
    )

    heading_style = ParagraphStyle(
        "ResearchHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2447A5"),
        spaceBefore=12,
        spaceAfter=8
    )

    body_style = ParagraphStyle(
        "ResearchBody",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=14,
        spaceAfter=7
    )

    story = [
        Paragraph("ResearchOS", title_style),
        Paragraph(escape(topic), heading_style),
        Paragraph(
            f"Generated: {escape(created_at)}",
            body_style
        ),
        Spacer(1, 12)
    ]

    for line in report.splitlines():

        line = line.strip()

        if not line:
            story.append(Spacer(1, 5))

        elif line.startswith("# "):
            story.append(
                Paragraph(escape(line[2:]), heading_style)
            )

        elif line.startswith("## "):
            story.append(
                Paragraph(escape(line[3:]), heading_style)
            )

        elif line.startswith("### "):
            story.append(
                Paragraph(
                    f"<b>{escape(line[4:])}</b>",
                    body_style
                )
            )

        elif line.startswith(("- ", "* ")):
            story.append(
                Paragraph(
                    "• " + escape(line[2:]),
                    body_style
                )
            )

        else:
            clean = re.sub(
                r"\*\*(.*?)\*\*",
                r"\1",
                line
            )

            clean = re.sub(
                r"\*(.*?)\*",
                r"\1",
                clean
            )

            story.append(
                Paragraph(escape(clean), body_style)
            )

    document.build(story)

    buffer.seek(0)

    return buffer.getvalue()


# =====================================================
# 8. SESSION STATE
# =====================================================

if "current_report" not in st.session_state:
    st.session_state.current_report = None


# =====================================================
# 9. CUSTOM DESIGN
# =====================================================

st.markdown("""
<style>

.stApp {
    background: linear-gradient(
        135deg,
        #07111f,
        #101a2d
    );
    color: #e8eefc;
}

section[data-testid="stSidebar"] {
    background: #08101d;
    border-right: 1px solid #23334c;
}

.hero {
    padding: 28px;
    border-radius: 18px;
    background: linear-gradient(
        120deg,
        #10294c,
        #17213a
    );
    border: 1px solid #30476b;
    margin-bottom: 25px;
}

.hero h1 {
    color: white;
    font-size: 36px;
}

.hero p {
    color: #b9c9e8;
}

.metric-card {
    background: #111d31;
    border: 1px solid #263a5b;
    border-radius: 12px;
    padding: 18px;
    text-align: center;
}

.metric-card h2 {
    color: #75a9ff;
    margin: 0;
}

.metric-card p {
    color: #a8b8d4;
}

div.stButton > button {
    border-radius: 9px;
    border: 1px solid #3a5e9a;
}

.footer {
    color: #7186a6;
    text-align: center;
    font-size: 12px;
    padding: 20px;
}

</style>
""", unsafe_allow_html=True)


# =====================================================
# 10. SIDEBAR
# =====================================================

with st.sidebar:

    st.markdown("## 🔬 ResearchOS")

    st.caption("AI Research Intelligence")

    page = st.radio(
        "Navigation",
        [
            "Research Workspace",
            "Research History",
            "About ResearchOS"
        ]
    )

    st.divider()

    st.markdown("### System Status")

    if client:
        st.success("Gemini API configured")
    else:
        st.error("Gemini API key missing")

    st.caption(f"Model: {MODEL_NAME}")
    st.caption("Live Search: Disabled")


# =====================================================
# 11. HEADER
# =====================================================

st.markdown("""
<div class="hero">

    <h1>🔬 ResearchOS</h1>

    <p>AI-powered research intelligence workspace</p>

    <p>
        Discover insights. Analyze ideas.
        Generate research reports.
    </p>

</div>
""", unsafe_allow_html=True)


# =====================================================
# 12. RESEARCH WORKSPACE
# =====================================================

if page == "Research Workspace":

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="metric-card">
            <h2>AI</h2>
            <p>Research Engine</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="metric-card">
            <h2>Knowledge</h2>
            <p>Gemini AI Analysis</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="metric-card">
            <h2>PDF</h2>
            <p>Research Export</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    st.subheader("🧠 Start a New Research Project")

    topic = st.text_area(
        "Research topic",
        placeholder=(
            "Example: Agentic AI applications "
            "in healthcare"
        ),
        height=100
    )

    col1, col2 = st.columns(2)

    with col1:

        depth = st.selectbox(
            "Research depth",
            [
                "Quick Overview",
                "Standard Research",
                "Deep Research"
            ],
            index=1
        )

    with col2:

        style = st.selectbox(
            "Report style",
            [
                "Professional Academic",
                "Beginner Friendly",
                "Technical",
                "Executive Summary"
            ]
        )

    generate_button = st.button(
        "🚀 Start Research Project",
        type="primary",
        use_container_width=True
    )

    if generate_button:

        if not API_KEY:

            st.error(
                "GEMINI_API_KEY is missing. "
                "Configure it in Streamlit Cloud Secrets "
                "or your local .env file."
            )

        elif not topic.strip():

            st.warning("Please enter a research topic.")

        else:

            with st.spinner(
                "ResearchOS is analyzing your topic..."
            ):

                try:

                    report, sources = generate_research(
                        topic.strip(),
                        depth,
                        style
                    )

                    created_at = datetime.now().strftime(
                        "%d %b %Y, %I:%M %p"
                    )

                    save_report(
                        topic.strip(),
                        report,
                        sources,
                        created_at
                    )

                    st.session_state.current_report = {
                        "topic": topic.strip(),
                        "report": report,
                        "created_at": created_at
                    }

                except Exception as error:

                    show_ai_error(error)

    # DISPLAY REPORT

    current = st.session_state.current_report

    if current:

        st.divider()

        st.subheader("📄 Research Report")

        st.caption(
            f"Topic: {current['topic']} | "
            f"Generated: {current['created_at']}"
        )

        st.markdown(current["report"])

        st.info(
            "This report uses Gemini's learned knowledge. "
            "Live web search is disabled. Independently "
            "verify recent developments and important facts."
        )

        st.divider()

        st.subheader("📥 Export Your Research")

        try:

            pdf_data = create_pdf(
                current["topic"],
                current["report"],
                current["created_at"]
            )

            col1, col2 = st.columns(2)

            with col1:

                st.download_button(
                    "📥 Download Markdown",
                    data=current["report"],
                    file_name="ResearchOS_Report.md",
                    mime="text/markdown",
                    use_container_width=True
                )

            with col2:

                st.download_button(
                    "📑 Download PDF",
                    data=pdf_data,
                    file_name="ResearchOS_Report.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

        except Exception as error:

            st.error(f"PDF generation error: {error}")


# =====================================================
# 13. RESEARCH HISTORY
# =====================================================

elif page == "Research History":

    st.subheader("📚 Research History")

    reports = get_reports()

    if not reports:

        st.info("No saved research reports yet.")

    else:

        st.caption(
            f"{len(reports)} saved research projects"
        )

        for item in reports:

            with st.expander(
                f"📄 {item['topic']} — {item['created_at']}"
            ):

                st.markdown(item["report"])

                col1, col2 = st.columns(2)

                with col1:

                    st.download_button(
                        "📥 Download Markdown",
                        data=item["report"],
                        file_name=f"Research_{item['id']}.md",
                        mime="text/markdown",
                        key=f"md_{item['id']}",
                        use_container_width=True
                    )

                with col2:

                    pdf_data = create_pdf(
                        item["topic"],
                        item["report"],
                        item["created_at"]
                    )

                    st.download_button(
                        "📑 Download PDF",
                        data=pdf_data,
                        file_name=f"Research_{item['id']}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{item['id']}",
                        use_container_width=True
                    )

                if st.button(
                    "🗑️ Delete Report",
                    key=f"delete_{item['id']}"
                ):

                    delete_report(item["id"])
                    st.rerun()


# =====================================================
# 14. ABOUT
# =====================================================

elif page == "About ResearchOS":

    st.subheader("About ResearchOS")

    st.markdown("""
## 🔬 ResearchOS

ResearchOS is an AI-powered research assistant
designed to help users explore topics, understand
concepts, and generate structured reports.

### Features

- Gemini AI research generation
- Structured research reports
- Research history
- PDF export
- Markdown export

### Technology Stack

- Python
- Streamlit
- Google Gemini API
- SQLite
- ReportLab

### Search Capability

Live Google Search grounding is disabled in this
version. Reports use the model's learned knowledge
and should be independently verified for current
information.
""")


# =====================================================
# 15. FOOTER
# =====================================================

st.markdown("""
<div class="footer">
    RESEARCHOS · AI RESEARCH INTELLIGENCE ·
    BUILT WITH PYTHON
</div>
""", unsafe_allow_html=True)
