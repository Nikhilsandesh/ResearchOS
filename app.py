
import os
import re
import io
import sqlite3
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
)
from reportlab.lib.units import mm
from xml.sax.saxutils import escape


# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="ResearchOS",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

MODEL_NAME = "gemini-3.8-flash"

DB_PATH = os.path.join(os.path.dirname(__file__), "researchos.db")


# =========================================================
# GEMINI CLIENT
# =========================================================

@st.cache_resource
def get_client():
    if not API_KEY:
        return None
    return genai.Client(api_key=API_KEY)


client = get_client()


# =========================================================
# DATABASE
# =========================================================

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                report TEXT NOT NULL,
                sources TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def save_report(topic, report, sources, created_at):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO reports (topic, report, sources, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (topic, report, "\n".join(sources), created_at),
        )
        conn.commit()


def get_reports():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM reports ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def delete_report(report_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        conn.commit()


init_db()


# =========================================================
# PDF GENERATOR
# =========================================================

def create_pdf(topic, report, sources, created_at):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=topic,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ResearchTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=28,
        textColor=colors.HexColor("#243B80"),
        alignment=TA_CENTER,
        spaceAfter=18,
    )

    heading_style = ParagraphStyle(
        "ResearchHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2447A5"),
        spaceBefore=12,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "ResearchBody",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=14,
        spaceAfter=7,
    )

    story = []

    story.append(Paragraph("ResearchOS", title_style))
    story.append(Paragraph(escape(topic), heading_style))
    story.append(Paragraph(
        f"Generated: {escape(created_at)}",
        body_style,
    ))
    story.append(Spacer(1, 12))

    for line in report.splitlines():
        line = line.strip()

        if not line:
            story.append(Spacer(1, 5))
            continue

        if line.startswith("# "):
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
                    body_style,
                )
            )

        elif line.startswith("- ") or line.startswith("* "):
            story.append(
                Paragraph(
                    "• " + escape(line[2:]),
                    body_style,
                )
            )

        else:
            clean_line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            clean_line = re.sub(r"\*(.*?)\*", r"\1", clean_line)
            story.append(Paragraph(escape(clean_line), body_style))

    if sources:
        story.append(Spacer(1, 15))
        story.append(Paragraph("Sources", heading_style))

        for index, source in enumerate(sources, 1):
            story.append(
                Paragraph(
                    f"{index}. {escape(source)}",
                    body_style,
                )
            )

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# =========================================================
# RESEARCH GENERATION
# =========================================================

def generate_research(topic, depth, style):
    prompt = f"""
You are ResearchOS, an intelligent AI research assistant.

Research topic:
{topic}

Research depth:
{depth}

Writing style:
{style}

Create a detailed, useful, well-structured research report.

Include:
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

Use clear headings and Markdown formatting.
Explain difficult concepts in understandable language.
Use factual information and avoid inventing statistics.
Cite sources or evidence when available.
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    google_search=types.GoogleSearch()
                )
            ]
        ),
    )

    report_text = response.text or "No report generated."

    sources = []

    try:
        grounding = response.candidates[0].grounding_metadata

        if grounding and grounding.grounding_chunks:
            for chunk in grounding.grounding_chunks:
                if chunk.web and chunk.web.uri:
                    source = chunk.web.uri

                    if source not in sources:
                        sources.append(source)

    except Exception:
        pass

    return report_text, sources


# =========================================================
# SESSION STATE
# =========================================================

if "current_report" not in st.session_state:
    st.session_state.current_report = None

if "research_count" not in st.session_state:
    st.session_state.research_count = 0


# =========================================================
# CUSTOM UI
# =========================================================

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #07111f, #101a2d);
    color: #e8eefc;
}

section[data-testid="stSidebar"] {
    background: #08101d;
    border-right: 1px solid #23334c;
}

.hero {
    padding: 28px;
    border-radius: 18px;
    background: linear-gradient(120deg, #10294c, #17213a);
    border: 1px solid #30476b;
    margin-bottom: 25px;
}

.hero h1 {
    color: #ffffff;
    font-size: 36px;
    margin-bottom: 5px;
}

.hero p {
    color: #b9c9e8;
    font-size: 15px;
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
    margin-bottom: 0;
}

div.stButton > button {
    border-radius: 9px;
    border: 1px solid #3a5e9a;
}

.stDownloadButton button {
    width: 100%;
    border-radius: 9px;
}

.report-box {
    background: #0e192a;
    border: 1px solid #243854;
    border-radius: 12px;
    padding: 18px;
}

.footer {
    color: #7186a6;
    text-align: center;
    font-size: 12px;
    padding: 20px;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown("## 🔬 ResearchOS")
    st.caption("AI Research Intelligence")

    page = st.radio(
        "Navigation",
        [
            "Research Workspace",
            "Research History",
            "About ResearchOS",
        ],
    )

    st.divider()

    st.markdown("### System Status")

    if client:
        st.success("Gemini API configured")
    else:
        st.error("Gemini API key missing")

    st.caption(f"Model: {MODEL_NAME}")


# =========================================================
# HEADER
# =========================================================

st.markdown("""
<div class="hero">
    <h1>🔬 ResearchOS</h1>
    <p>AI-powered research intelligence workspace</p>
    <p>Discover insights. Analyze ideas. Generate research reports.</p>
</div>
""", unsafe_allow_html=True)


# =========================================================
# RESEARCH WORKSPACE
# =========================================================

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
            <h2>Web</h2>
            <p>Google Search Grounding</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="metric-card">
            <h2>PDF</h2>
            <p>Exportable Reports</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    st.subheader("🧠 Start a New Research Project")

    topic = st.text_area(
        "Research topic",
        placeholder="Example: Agentic AI applications in healthcare",
        height=100,
    )

    col1, col2 = st.columns(2)

    with col1:
        depth = st.selectbox(
            "Research depth",
            [
                "Quick Overview",
                "Standard Research",
                "Deep Research",
            ],
            index=1,
        )

    with col2:
        style = st.selectbox(
            "Report style",
            [
                "Professional Academic",
                "Beginner Friendly",
                "Technical",
                "Executive Summary",
            ],
        )

    generate_button = st.button(
        "🚀 Start Research Project",
        type="primary",
        use_container_width=True,
    )

    if generate_button:

        if not API_KEY:
            st.error(
                "GEMINI_API_KEY is missing. "
                "Add it to your .env file."
            )

        elif not topic.strip():
            st.warning("Please enter a research topic.")

        else:
            with st.spinner(
                "ResearchOS is researching your topic..."
            ):
                try:
                    report, sources = generate_research(
                        topic.strip(),
                        depth,
                        style,
                    )

                    created_at = datetime.now().strftime(
                        "%d %b %Y, %I:%M %p"
                    )

                    save_report(
                        topic.strip(),
                        report,
                        sources,
                        created_at,
                    )

                    st.session_state.current_report = {
                        "topic": topic.strip(),
                        "report": report,
                        "sources": sources,
                        "created_at": created_at,
                    }

                    st.session_state.research_count += 1

                except Exception as error:
                    st.error(f"Research failed: {error}")

    # -----------------------------------------------------
    # DISPLAY REPORT
    # -----------------------------------------------------

    current = st.session_state.current_report

    if current:

        st.divider()

        st.subheader("📄 Research Report")
        st.caption(
            f"Topic: {current['topic']} | "
            f"Generated: {current['created_at']}"
        )

        st.markdown(
            current["report"],
            unsafe_allow_html=False,
        )

        # -------------------------------------------------
        # SOURCES
        # -------------------------------------------------

        if current["sources"]:
            st.subheader("🔗 Research Sources")

            for index, source in enumerate(
                current["sources"], 1
            ):
                st.markdown(
                    f"{index}. [{source}]({source})"
                )

        else:
            st.info(
                "Google Search did not return source links "
                "for this report."
            )

        # -------------------------------------------------
        # DOWNLOADS
        # -------------------------------------------------

        st.divider()
        st.subheader("📥 Export Your Research")

        try:
            pdf_data = create_pdf(
                current["topic"],
                current["report"],
                current["sources"],
                current["created_at"],
            )

            col1, col2 = st.columns(2)

            with col1:
                st.download_button(
                    label="📥 Download Markdown",
                    data=current["report"],
                    file_name="ResearchOS_Report.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

            with col2:
                st.download_button(
                    label="📑 Download PDF",
                    data=pdf_data,
                    file_name="ResearchOS_Report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

            st.success("PDF and Markdown exports are ready.")

        except Exception as error:
            st.error(f"PDF generation error: {error}")


# =========================================================
# RESEARCH HISTORY
# =========================================================

elif page == "Research History":

    st.subheader("📚 Research History")

    reports = get_reports()

    if not reports:
        st.info("No research reports saved yet.")

    else:
        st.caption(f"{len(reports)} saved research projects")

        for item in reports:

            with st.expander(
                f"📄 {item['topic']} — {item['created_at']}"
            ):

                st.markdown(item["report"])

                sources = (
                    item["sources"].splitlines()
                    if item["sources"]
                    else []
                )

                col1, col2 = st.columns(2)

                with col1:
                    st.download_button(
                        "📥 Download Markdown",
                        data=item["report"],
                        file_name=f"Research_{item['id']}.md",
                        mime="text/markdown",
                        key=f"md_{item['id']}",
                        use_container_width=True,
                    )

                with col2:
                    pdf_data = create_pdf(
                        item["topic"],
                        item["report"],
                        sources,
                        item["created_at"],
                    )

                    st.download_button(
                        "📑 Download PDF",
                        data=pdf_data,
                        file_name=f"Research_{item['id']}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{item['id']}",
                        use_container_width=True,
                    )

                if st.button(
                    "🗑️ Delete Report",
                    key=f"delete_{item['id']}",
                ):
                    delete_report(item["id"])
                    st.rerun()


# =========================================================
# ABOUT
# =========================================================

elif page == "About ResearchOS":

    st.subheader("About ResearchOS")

    st.markdown("""
    **ResearchOS** is an AI-powered research assistant
    designed to help users explore topics, understand
    concepts, and generate structured research reports.

    ### Features

    - Gemini AI research generation
    - Google Search grounding
    - Structured research reports
    - Persistent SQLite research history
    - PDF report export
    - Markdown report export

    ### Technology Stack

    - Python
    - Streamlit
    - Google Gemini API
    - Google Search grounding
    - SQLite
    - ReportLab
    """)


# =========================================================
# FOOTER
# =========================================================

st.markdown("""
<div class="footer">
    RESEARCHOS · AI RESEARCH INTELLIGENCE · BUILT WITH PYTHON
</div>
""", unsafe_allow_html=True)
