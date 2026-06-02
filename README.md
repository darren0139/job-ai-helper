# Job AI Helper

## 1. Project Title and Description

**Job AI Helper** is an AI-powered resume and job application assistant for DigiPen students and junior applicants.

The application lets a user upload a resume, paste a job description, analyse resume-job fit, identify skill gaps, generate a tailored cover letter, revise the cover letter through follow-up requests, and save multiple application sessions locally.

## 2. Problem Statement

Students often apply to multiple internships or junior roles, but it can be difficult to understand how well a resume matches each job description. Job descriptions can contain many required skills, preferred skills, tools, and soft-skill expectations, and manually comparing them against a resume is time-consuming.

This application helps by using AI to structure the resume and job description, compare them, explain missing keywords, generate a tailored cover letter, and save each job application analysis for later review.

## 3. Technology Stack

- **Language:** Python 3.10+
- **Web framework:** Streamlit
- **AI API wrapper:** LiteLLM
- **AI model route:** OpenAI through `MODEL=openai/gpt-4o-mini`
- **Environment variables:** python-dotenv
- **Resume parsing:** pypdf for PDF resumes, python-docx for DOCX resumes
- **Database:** SQLite
- **Report output:** JSON and Markdown downloads

Main files:

```text
app.py
parse.py
analyzer.py
prompts.py
llm.py
report.py
database/db_manager.py
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

Windows PowerShell:

```bash
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
```

### 4. Create your `.env` file

Copy `.env.example` to `.env`.

Windows PowerShell:

```bash
copy .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Example `.env.example`:

```env
MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=your_openai_api_key_here
```

Do not commit your real `.env` file to GitHub.

### 5. Run the application

```bash
streamlit run app.py
```

### 6. Use the app

1. Upload a text-based PDF or DOCX resume.
2. Paste a full job description.
3. Select the applicant degree programme.
4. Click **Analyze Resume**.
5. Review the scores, keyword match, bullet quality, structure audit, jargon audit, and degree fit.
6. Generate a tailored cover letter.
7. Ask for cover letter revisions.
8. Load saved application sessions from the sidebar.

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
The app restores the saved analysis report and any generated cover letter for Job A.
```

## 6. Known Limitations

- The app works best with text-based PDF and DOCX resumes. Scanned/image-only resumes may not parse correctly.
- The score is a helpful estimate, not a real ATS guarantee.
- The AI may still make mistakes when interpreting vague job descriptions or broad skill requirements.
- The database is local SQLite storage, so it is suitable for a single-user local demo but not a production multi-user system.
- The app does not automatically apply for jobs or scrape job portals.
- The app does not use RAG in the current version. It sends the current resume, job description, and analysis report directly to the AI model.

## 7. Future Improvements

- Add RAG over saved application sessions so users can ask questions across many saved job applications.
- Add a job-search API such as Adzuna or Jooble to search Singapore job listings safely without scraping.
- Add cover letter version history instead of only saving the latest version.
- Add export to DOCX for generated cover letters.
- Add user accounts and cloud database storage for real multi-user deployment.
- Add a resume improvement plan that suggests truthful improvements without inventing experience.
