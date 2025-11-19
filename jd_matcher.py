from flask import Blueprint, render_template, request, redirect, url_for
import os, fitz
from sentence_transformers import SentenceTransformer, util



jd_blueprint = Blueprint("jd_match", __name__, template_folder="templates")

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

model = SentenceTransformer('all-MiniLM-L6-v2')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == "pdf"

def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text


@jd_blueprint.route("/", methods=["GET", "POST"])
def jd_match_page():
    return render_template("jd_index.html")

@jd_blueprint.route("/results", methods=["POST"])
def jd_results():
    job_description = request.form["job_description"]
    uploaded_files = request.files.getlist("resumes")

    candidates = []
    for file in uploaded_files:
        if file and allowed_file(file.filename):
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            resume_text = extract_text_from_pdf(file_path)
            candidates.append((file.filename, resume_text))

    jd_embedding = model.encode(job_description, convert_to_tensor=True)
    ranked_candidates = []
    for filename, resume_text in candidates:
        resume_embedding = model.encode(resume_text, convert_to_tensor=True)
        similarity = util.pytorch_cos_sim(jd_embedding, resume_embedding).item()
        ranked_candidates.append((filename, similarity))

    ranked_candidates.sort(key=lambda x: x[1], reverse=True)

    return render_template("jd_results.html", candidates=ranked_candidates)
