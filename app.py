
import os
import sqlite3
from datetime import datetime
from io import BytesIO

import streamlit as st
from dotenv import load_dotenv
from google import genai
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
)

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="ResearchOS | AI Research Assistant",
    page_icon="🔬",
    layout="wide",
)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

MODEL_NAME = "gemini-4-hydrogen"
DB_PATH = os.path.join(os.path.dirname(__file__), "researchos.db")


# --------------------------------------------------
# API KEY AND GEMINI CLIENT
# --------------------------------------------------

def get_api_key():
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass

    return os.getenv("GEMINI_API_KEY", "")


@st.cache_resource
def get_gemini_client(api_key):
    return genai.Client(api_key=api_key)


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def init_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                report TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def save_report(topic, report):
    created_at = datetime.now().strftime("%d %b %Y, %I:%M %p")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO reports (topic, report, created_at) VALUES (?, ?, ?)",
            (topic, report, created_at),
        )
        conn.commit()


def get_reports():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT id, topic, created_at FROM reports ORDER BY id DESC"
        ).fetchall()


def get_report(report_id):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT topic, report, created_at FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()


def delete_report(report_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        conn.commit()


# --------------------------------------------------
# RESEARCH GENERATION
# --------------------------------------------------

def generate_research(client, topic, depth, style):

    prompt = f"""
You are ResearchOS, an AI research assistant.

Create a detailed and well-organized research report.

RESEARCH TOPIC:
{topic}

RESEARCH DEPTH:
{depth}

WRITING STYLE:
{style}

Follow this structure:

# 1. Executive Summary
Provide a clear overview of the research topic.

# 2. Introduction
Explain the topic and its importance.

# 3. Background
Explain its history, origin, and development.

# 4. Key Concepts
Explain the important concepts in detail.

# 5. Detailed Analysis
Analyze the topic with relevant explanations,
examples, applications, and important findings.

# 6. Current Developments
Discuss recent developments only when you can
reliably support them. Clearly identify information
that may require current verification.

# 7. Benefits and Applications
Explain practical uses and advantages.

# 8. Challenges and Limitations
Discuss major problems and limitations.

# 9. Future Scope
Explain possible future developments.

# 10. Conclusion
Summarize the main findings.

IMPORTANT INSTRUCTIONS:
- Use clear headings and subheadings.
- Explain technical terms simply.
- Use examples wherever useful.
- Avoid repeating the same information.
- Do not invent statistics, studies, quotations, or citations.
- If a fact is uncertain, clearly say so.
- Do not pretend to have searched the internet.
- Write a useful, structured research report.
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    return response.text


# --------------------------------------------------
# PDF GENERATION
# --------------------------------------------------

def create_pdf(topic, report):

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=21,
        leading=27,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#2563EB"),
        spaceAfter=18,
    )

    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#2563EB"),
        spaceBefore=14,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=15,
        spaceAfter=8,
    )

    story = [
        Paragraph("ResearchOS", title_style),
        Paragraph(topic.replace("&", "&amp;"), styles["Heading2"]),
        Paragraph(
            "Generated on " + datetime.now().strftime("%d %B %Y"),
            styles["Italic"],
        ),
        Spacer(1, 20),
    ]

    import re
    from xml.sax.saxutils import escape

    for line in report.splitlines():

        line = line.strip()

        if not line:
            story.append(Spacer(1, 5))
            continue

        if line.startswith("#"):
            heading = re.sub(r"^#+\s*", "", line)
            story.append(Paragraph(escape(heading), heading_style))

        elif line.startswith("- ") or line.startswith("* "):
            item = escape(line[2:])
            story.append(
                Paragraph("&#8226; " + item, body_style)
            )

        else:
            clean_line = escape(line)
            clean_line = re.sub(
                r"\*\*(.*?)\*\*",
                r"<b>\1</b>",
                clean_line,
            )
            story.append(Paragraph(clean_line, body_style))

    document.build(story)

    buffer.seek(0)
    return buffer.getvalue()


# --------------------------------------------------
# CUSTOM CSS
# --------------------------------------------------

st.markdown("""
<style>
.stApp {
    background-color: #0b1120;
    color: #f1f5f9;
}

section[data-testid="stSidebar"] {
    background-color: #111827;
}

.main-title {
    font-size: 38px;
    font-weight: 800;
    color: #60a5fa;
    margin-bottom: 0;
}

.subtitle {
    color: #94a3b8;
    font-size: 16px;
    margin-top: 5px;
    margin-bottom: 25px;
}

div.stButton > button {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 9px;
    padding: 10px 20px;
    font-weight: 600;
}

div.stButton > button:hover {
    background-color: #1d4ed8;
    color: white;
}

.report-box {
    background-color: #111827;
    border: 1px solid #263449;
    border-radius: 12px;
    padding: 18px;
}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# INITIALIZATION
# --------------------------------------------------

init_database()

if "generated_report" not in st.session_state:
    st.session_state.generated_report = None

if "generated_topic" not in st.session_state:
    st.session_state.generated_topic = None


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

st.sidebar.markdown("## 🔬 ResearchOS")
st.sidebar.caption("Your AI-powered research workspace")

page = st.sidebar.radio(
    "Navigation",
    [
        "Research Workspace",
        "Research History",
        "About ResearchOS",
    ],
)

st.sidebar.divider()
st.sidebar.caption("Powered by Google Gemini")


# --------------------------------------------------
# PAGE 1: RESEARCH WORKSPACE
# --------------------------------------------------

if page == "Research Workspace":

    st.markdown(
        '<p class="main-title">ResearchOS 🔬</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="subtitle">Your intelligent AI research assistant</p>',
        unsafe_allow_html=True,
    )

    st.markdown("### Start your research")

    topic = st.text_area(
        "Research Topic",
        placeholder="Example: Applications of Generative AI in Healthcare",
        height=110,
    )

    col1, col2 = st.columns(2)

    with col1:
        depth = st.selectbox(
            "Research Depth",
            [
                "Basic",
                "Intermediate",
                "Detailed",
            ],
        )

    with col2:
        style = st.selectbox(
            "Writing Style",
            [
                "Academic",
                "Professional",
                "Beginner Friendly",
            ],
        )

    generate_button = st.button(
        "🚀 Generate Research Report",
        use_container_width=True,
    )

    if generate_button:

        if not topic.strip():
            st.warning("Please enter a research topic.")

        else:
            api_key = get_api_key()

            if not api_key:
                st.error(
                    "Gemini API key not found. "
                    "Add GEMINI_API_KEY to your .env file "
                    "or Streamlit Cloud Secrets."
                )

            else:
                try:
                    client = get_gemini_client(api_key)

                    with st.spinner(
                        "ResearchOS is generating your report..."
                    ):
                        report = generate_research(
                            client,
                            topic.strip(),
                            depth,
                            style,
                        )

                    save_report(topic.strip(), report)

                    st.session_state.generated_report = report
                    st.session_state.generated_topic = topic.strip()

                    st.success("Research report generated successfully!")

                except Exception as error:

                    error_message = str(error)

                    if "503" in error_message or "UNAVAILABLE" in error_message:
                        st.error(
                            "Gemini is temporarily experiencing high demand. "
                            "Please wait a few minutes and try again."
                        )

                    elif "429" in error_message or "RESOURCE_EXHAUSTED" in error_message:
                        st.error(
                            "Gemini API quota or rate limit reached. "
                            "Check your Google AI Studio usage and quota."
                        )

                    elif "404" in error_message or "NOT_FOUND" in error_message:
                        st.error(
                            "The selected Gemini model was not found "
                            "or is unavailable for this API key."
                        )

                    else:
                        st.error("Research generation failed.")
                        st.caption(error_message)

    # DISPLAY GENERATED REPORT

    if st.session_state.generated_report:

        st.divider()
        st.markdown("## 📄 Your Research Report")

        st.markdown(
            f"**Topic:** {st.session_state.generated_topic}"
        )

        report = st.session_state.generated_report
        report_topic = st.session_state.generated_topic

        st.markdown('<div class="report-box">', unsafe_allow_html=True)
        st.markdown(report)
        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        pdf_file = create_pdf(report_topic, report)

        safe_name = "".join(
            c if c.isalnum() else "_"
            for c in report_topic[:40]
        ).strip("_")

        file_name = safe_name or "research_report"

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                "📥 Download PDF",
                data=pdf_file,
                file_name=f"{file_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        with col2:
            st.download_button(
                "📥 Download Markdown",
                data=report,
                file_name=f"{file_name}.md",
                mime="text/markdown",
                use_container_width=True,
            )


# --------------------------------------------------
# PAGE 2: RESEARCH HISTORY
# --------------------------------------------------

elif page == "Research History":

    st.markdown("## 📚 Research History")
    st.caption("View your previously generated research reports.")

    reports = get_reports()

    if not reports:
        st.info("No research reports saved yet.")

    else:
        for report_id, topic, created_at in reports:

            with st.expander(
                f"📄 {topic} — {created_at}"
            ):

                saved = get_report(report_id)

                if saved:

                    saved_topic, saved_report, saved_date = saved

                    st.markdown(saved_report)

                    pdf_file = create_pdf(
                        saved_topic,
                        saved_report,
                    )

                    safe_name = "".join(
                        c if c.isalnum() else "_"
                        for c in saved_topic[:40]
                    ).strip("_") or "research_report"

                    st.download_button(
                        "📥 Download PDF",
                        data=pdf_file,
                        file_name=f"{safe_name}.pdf",
                        mime="application/pdf",
                        key=f"download_{report_id}",
                    )

                    if st.button(
                        "🗑️ Delete Report",
                        key=f"delete_{report_id}",
                    ):
                        delete_report(report_id)
                        st.rerun()


# --------------------------------------------------
# PAGE 3: ABOUT
# --------------------------------------------------

elif page == "About ResearchOS":

    st.markdown("## 🔬 About ResearchOS")

    st.write(
        """
        ResearchOS is an AI-powered research assistant designed
        to help users explore topics and generate structured
        research reports.

        ### Features

        - AI-powered research generation
        - Multiple research depth options
        - Different writing styles
        - Research history management
        - PDF report export
        - Markdown report export

        ### Technology Stack

        - Python
        - Streamlit
        - Google Gemini API
        - SQLite
        - ReportLab

        ### Purpose

        ResearchOS aims to make research easier by helping users
        organize information into clear and structured reports.
        """
    )

    st.divider()

    st.markdown("**ResearchOS | AI Research Assistant**")
    st.caption("Built as an Agentic AI portfolio project.")
