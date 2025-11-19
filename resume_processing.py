import io
import base64
from pdfminer3.layout import LAParams
from pdfminer3.pdfpage import PDFPage
from pdfminer3.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer3.converter import TextConverter
from pyresparer.resume_parser import ResumeParser


try:
    from Courses import (
        ds_course,
        web_course,
        android_course,
        ios_course,
        uiux_course,
    )
except Exception:
    ds_course = web_course = android_course = ios_course = uiux_course = []


def analyze_resume(file_path):
  data = ResumeParser(file_path).get_extracted_data()
  return {
  "name": data.get("name"),
  "email": data.get("email"),
  "mobile_number": data.get("mobile_number"),
  "skills": data.get("skills", []),
  "degree": data.get("degree"),
  "no_of_pages": data.get("no_of_pages"),
  }


def pdf_reader(file_path: str) -> str:
    resource_manager = PDFResourceManager()
    fake_file_handle = io.StringIO()
    converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams())
    page_interpreter = PDFPageInterpreter(resource_manager, converter)
    with open(file_path, 'rb') as fh:
        for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
            page_interpreter.process_page(page)
    text = fake_file_handle.getvalue()
    converter.close()
    fake_file_handle.close()
    return text


def show_pdf_iframe(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    return f'<iframe src="data:application/pdf;base64,{b64}" width="700" height="1000" type="application/pdf"></iframe>'


def detect_candidate_level(extracted: dict, resume_text: str):
    pages = (extracted or {}).get('no_of_pages') or 0
    text = resume_text or ''
    if pages < 1:
        return "NA", "You are at Fresher level!"

    t = text.lower()
    if any(k in t for k in ["internship", "internships"]):
        return "Intermediate", "You are at intermediate level!"
    if any(k in t for k in ["work experience", "experience"]):
        return "Experienced", "You are at experience level!"
    return "Fresher", "You are at Fresher level!"


def recommend_field_and_skills(extracted: dict):
    skills = [s.lower() for s in (extracted or {}).get('skills') or []]

    ds_keyword = ['tensorflow','keras','pytorch','machine learning','deep learning','flask','streamlit']
    web_keyword = ['react','django','node js','react js','php','laravel','magento','wordpress','javascript','angular js','c#','asp.net','flask']
    android_keyword = ['android','android development','flutter','kotlin','xml','kivy']
    ios_keyword = ['ios','ios development','swift','cocoa','cocoa touch','xcode']
    uiux_keyword = ['ux','adobe xd','figma','zeplin','balsamiq','ui','prototyping','wireframes','storyframes','adobe photoshop','photoshop','editing','adobe illustrator','illustrator','adobe after effects','after effects','adobe premier pro','premier pro','adobe indesign','indesign','wireframe']

    field = 'NA'
    rec_skills = []
    courses = []

    if any(s in ds_keyword for s in skills):
        field = 'Data Science'
        rec_skills = ['Data Visualization','Predictive Analysis','Statistical Modeling','Data Mining','Clustering & Classification','Data Analytics','Quantitative Analysis','Web Scraping','ML Algorithms','Keras','Pytorch','Probability','Scikit-learn','Tensorflow','Flask','Streamlit']
        courses = ds_course
    elif any(s in web_keyword for s in skills):
        field = 'Web Development'
        rec_skills = ['React','Django','Node JS','React JS','PHP','Laravel','Magento','WordPress','JavaScript','AngularJS','C#','Flask','SDK']
        courses = web_course
    elif any(s in android_keyword for s in skills):
        field = 'Android Development'
        rec_skills = ['Android','Flutter','Kotlin','XML','Java','Kivy','GIT','SDK','SQLite']
        courses = android_course
    elif any(s in ios_keyword for s in skills):
        field = 'IOS Development'
        rec_skills = ['Swift','Cocoa','Cocoa Touch','Xcode','Objective-C','SQLite','Plist','StoreKit','UI-Kit','AV Foundation','Auto-Layout']
        courses = ios_course
    elif any(s in uiux_keyword for s in skills):
        field = 'UI-UX Development'
        rec_skills = ['UI','User Experience','Adobe XD','Figma','Zeplin','Balsamiq','Prototyping','Wireframes','Storyframes','Photoshop','Illustrator','After Effects','Premier Pro','Indesign','User Research']
        courses = uiux_course

    return {"field": field, "skills": rec_skills, "courses": courses}


def score_resume(resume_text: str):
    t = (resume_text or '').lower()

    checks = [
        (any(k in t for k in ["objective", "summary"]) , "Objective/Summary" , 6),
        (any(k in t for k in ["education","school","college"]) , "Education" , 12),
        ("experience" in t , "Experience" , 16),
        ("internship" in t , "Internships" , 6),
        (any(k in t for k in ["skills","skill"]) , "Skills" , 7),
        ("hobbies" in t , "Hobbies" , 4),
        ("interests" in t , "Interests" , 5),
        ("achievements" in t , "Achievements" , 13),
        (any(k in t for k in ["certifications","certification"]) , "Certifications" , 12),
        (any(k in t for k in ["projects","project"]) , "Projects" , 19),
    ]

    score = 0
    tips = []
    progress = []

    for ok, label, pts in checks:
        if ok:
            score += pts
            progress.append({"label": label, "ok": True, "points": pts})
        else:
            tips.append(f"Add {label} section to strengthen your resume.")
            progress.append({"label": label, "ok": False, "points": 0})

    score = max(0, min(score, 100))
    return score, tips, progress