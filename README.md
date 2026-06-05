# Job AI Helper

## 1. Project Title and Description

**Job AI Helper** is an AI-powered resume and job application assistant for students and junior applicants.

The application lets a user upload a resume, paste a job description, analyse resume-job fit, identify skill gaps, generate a tailored cover letter, revise the cover letter through follow-up requests, and save multiple application sessions locally.

The app also includes a **Job Market Insights** page using **ChromaDB RAG**. Every time the user analyses a job description through **Analyze Resume**, the job description is saved and indexed. The user can then ask questions across all analysed job descriptions, upload or paste a separate resume for market comparison, and view a market-fit score based on recurring job requirements.

## 2. Problem Statement

Students often apply to multiple internships or junior roles, but it can be difficult to understand how well a resume matches each job description. Job descriptions can contain many required skills, preferred skills, tools, and soft-skill expectations, and manually comparing them against a resume is time-consuming.

This application helps by using AI to structure the resume and job description, compare them, explain missing keywords, generate a tailored cover letter, and save each job application analysis for later review.

The RAG feature extends this further by helping the user understand patterns across multiple analysed job descriptions, such as common skills, commonly requested tools, and areas where their resume may be weak across the job market.

## 3. Technology Stack

- **Language:** Python 3.10+
- **Web framework:** Streamlit
- **AI API wrapper:** LiteLLM
- **AI model route:** OpenAI through `MODEL=openai/gpt-4o-mini`
- **Embedding model:** OpenAI embedding route through `EMBEDDING_MODEL=openai/text-embedding-3-small`
- **Environment variables:** python-dotenv
- **Resume parsing:** pypdf for PDF resumes, python-docx for DOCX resumes
- **Database:** SQLite
- **Vector database:** ChromaDB
- **RAG:** ChromaDB vector retrieval over analysed job-description chunks
- **Report output:** JSON and Markdown downloads
- **Session storage:** SQLite-backed application sessions, cover letters, and chat history

Main files:

```text
app.py
parse.py
analyzer.py
prompts.py
llm.py
report.py
database/
  db_manager.py
  jd_library_manager.py
  chat_history_manager.py
rag/
  __init__.py
  jd_chroma_rag.py
requirements.txt
.env.example
README.md
```

## 4. Setup Instructions

### 1. Clone the repository

```bash
git clone <your-github-repository-url>
cd <your-repository-folder>
```

### 2. Create and activate a virtual environment

Windows CMD (Command):

```cmd
python -m venv .venv
.venv\Scripts\activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Your `requirements.txt` should include:

```text
litellm
python-dotenv
pypdf
python-docx
streamlit
openai
chromadb
```

### 4. Create your `.env` file

Copy `.env.example` to `.env`.

Windows CMD (Command):

```cmd
copy .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Example `.env.example`:

```env
MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=your_openai_api_key_here
EMBEDDING_MODEL=openai/text-embedding-3-small
```

Do not commit your real `.env` file to GitHub.

### 5. Check `.gitignore`

Recommended `.gitignore` entries:

```gitignore

# secrets
.env
.streamlit/secrets.toml

# python cache
__pycache__/
*.pyc

# virtual environment
venv/
.venv/

# output
outputs/*
!outputs/.gitkeep

# db stuff
.db
data/*.db
data/*.db-journal
data/*.sqlite
data/*.sqlite3
data/chroma_jd_library/

# Keep the data folder in Git
!data/.gitkeep
```

### 6. Run the application

```bash
streamlit run app.py
```

### 7. Use the app

1. Open the **Application Sessions** page from the sidebar.
2. Click **New Application Session**.
3. Upload a text-based PDF or DOCX resume.
4. Paste a full job description.
5. Click **Analyze Resume**.
6. Review the scores, keyword match, bullet quality, structure audit, jargon audit, and degree fit.
7. Generate a tailored cover letter.
8. Ask follow-up questions about the analysis.
9. Open the **Job Market Insights** page to use RAG across analysed job descriptions.

## 5. Usage Examples

### Example 1 — Resume-job analysis

**Input:**

```text
Resume: Software engineering student resume in DOCX format
Job description: Software Engineer Intern role requiring Python, REST APIs, SQL, cloud knowledge, and teamwork
Degree programme: IMGD
```

**Expected output:**

```text
Overall score: 75/100
Keyword match: Shows present and missing skills
Bullet quality: Identifies which bullets need stronger measurable impact
Structure: Checks ATS-friendly formatting
Degree fit: Explains how the role aligns with the selected degree
```

### Example 2 — Cover letter generation and revision

**Input:**

```text
Generate a cover letter for this job application.
```

**Expected output:**

```text
A professional 3-4 paragraph cover letter based on the resume profile, job description profile, and analysis summary.
```

**Follow-up request:**

```text
Make it shorter and more confident.
```

**Expected output:**

```text
A revised cover letter that keeps the facts accurate while changing the tone and length.
```

### Example 3 — Saved application sessions

**Input:**

```text
Analyze a resume against Job A.
Analyze the same resume against Job B.
Load Job A from the sidebar.
```

**Expected output:**

```text
The app restores the saved analysis report, generated cover letter, and saved follow-up chat for Job A.
```

The user can also rename or delete each application session from the sidebar.

### Example 4 — Ask about a saved application analysis

**Input:**

```text
What should I improve first for this job?
```

**Expected output:**

```text
The app answers using the current saved analysis report and stores the conversation in the application session chat history.
```

### Example 5 — Job Market Insights with RAG

**Input:**

After analysing multiple jobs, the user opens **Job Market Insights** and asks:

```text
What skills appear often in the jobs I analysed?
```

**Expected output:**

```text
The app retrieves relevant job-description chunks from ChromaDB and answers using the analysed job descriptions.
```

Example answer:

```text
Common recurring requirements include Python, SQL, communication, teamwork, REST APIs, and experience with data or backend workflows.
```

### Example 6 — Resume market-fit comparison

**Input:**

The user uploads or pastes a resume in the **Job Market Insights** page and clicks:

```text
Analyze Resume for Market Fit
```

**Expected output:**

```text
Market Fit Against Frequent JD Skills: 68/100
```

The app displays:

```text
Common Skills Already Shown
Common Skills Missing or Weakly Evidenced
Common JD terms used for scoring
```

This score is separate from the one-job resume score. It compares the uploaded market-comparison resume against skills that appear frequently across analysed job descriptions.

## 6. Known Limitations

- The app works best with text-based PDF and DOCX resumes. Scanned/image-only resumes may not parse correctly.
- Saved application sessions restore the analysis report, generated cover letter, and chat history, but they do **not** restore the original uploaded PDF or DOCX file. This is intentional for privacy because resumes contain personal information. To re-analyse, upload the resume again.
- The score is a helpful estimate, not a real ATS guarantee.
- The Market Fit Score is also an estimate. It uses extracted JD terms, term frequency, field weighting, and resume term matching, so it may miss some synonyms or over-match broad phrases.
- RAG depends on the job descriptions that have already been analysed. If only one or two jobs have been analysed, the Job Market Insights answers may be less representative.
- ChromaDB is stored locally in `data/chroma_jd_library/`, so this setup is suitable for a single-user local demo rather than a production multi-user deployment.
- The app does not automatically apply for jobs or scrape job portals.
- The AI may still make mistakes when interpreting vague job descriptions, broad requirements, or ambiguous resume experience.

## 7. Future Improvements

- Add duplicate detection so the same job description is not repeatedly saved or indexed when the user re-analyses the same role.
- Improve the Market Fit Score using stronger semantic matching instead of mainly term/token matching.
- Add source citations in RAG answers so users can see which analysed job descriptions supported each point.
- Add cover letter version history instead of only saving the latest version.
- Add export to DOCX for generated cover letters.
- Add optional secure resume-file storage per session, controlled by the user.
- Add user accounts and cloud database storage for real multi-user deployment.
- Add a job-search API such as Adzuna or Jooble to search Singapore job listings safely without scraping.
- Add a resume improvement plan that suggests truthful improvements without inventing experience.
