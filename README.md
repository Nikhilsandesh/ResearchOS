# 🔬 ResearchOS — AI Research Assistant

ResearchOS is an AI-powered research assistant built using Python, Streamlit and Google's Gemini API. It helps users generate structured research reports on different topics and download them in PDF and Markdown formats.

## ✨ Features

- 🤖 AI-powered research report generation
- 📝 Multiple research depth levels
- 🎨 Multiple writing styles
- 📚 Research history management
- 📄 PDF report downloads
- 📥 Markdown report downloads
- 💾 SQLite-based report storage
- 🌙 Dark-themed user interface

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Streamlit | Web application interface |
| Google Gemini API | AI report generation |
| SQLite | Local report storage |
| ReportLab | PDF generation |

## 🌐 Project Links

- **Live Demo:** [Open ResearchOS](https://nikhilsandesh-researchos-app-yods06.streamlit.app)
- **Source Code:** [View ResearchOS on GitHub]

## 🚀 Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/Nikhilsandesh/ResearchOS.git
cd ResearchOS
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on macOS:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your Gemini API key

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
```

Replace the example value with your own Gemini API key.

**Security:** Never upload your `.env` file or API key to GitHub.

For Streamlit Cloud, add the key under App Settings → Secrets.

### 5. Run the application

```bash
streamlit run app.py
```

The application will open in your browser.

## 📁 Project Structure

```text
ResearchOS/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env
└── researchos.db
```

**Note:** `.env`, `.venv/`, and `researchos.db` are excluded from GitHub using `.gitignore`.

## 👨‍💻 Developer

**Nikhil Sandesh**

B.Tech in Artificial Intelligence and Machine Learning  
Anurag University  
2024–2028

## 🎯 Project Objective

The objective of ResearchOS is to simplify research by using generative AI to transform user-provided topics into structured reports.

## 🔮 Future Enhancements

- Web search integration for verified research sources
- Source citations and references
- Multi-agent research workflow
- Advanced report customization
- Cloud-based research history

---

ResearchOS — Research Smarter with AI.