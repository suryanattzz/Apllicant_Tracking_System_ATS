import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from markupsafe import Markup
from werkzeug.utils import secure_filename
from datetime import datetime
from db import get_db, init_db
from resume_processing import (
    analyze_resume,
    pdf_reader,
    show_pdf_iframe,
    detect_candidate_level,
    score_resume,
    recommend_field_and_skills,
)
from jd_matcher import jd_blueprint


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-change-me")

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "Uploaded_Resumes")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.register_blueprint(jd_blueprint, url_prefix="/jd_match")

# Ensure DB/tables exist at startup
with app.app_context():
    init_db()

@app.route("/")
def home():
    return render_template("index.html")

@app.post("/analyze")
def analyze():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()

    f = request.files.get("resume")
    if not f or f.filename == "":
        flash("Please upload a PDF resume.")
        return redirect(url_for("home"))

    filename = secure_filename(f.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    f.save(save_path)

    # Extract
    extracted = analyze_resume(save_path)
    if not extracted:
        flash("Sorry, we could not parse your resume.")
        return redirect(url_for("home"))

    resume_text = pdf_reader(save_path)

    cand_level, level_msg = detect_candidate_level(extracted, resume_text)

    reco = recommend_field_and_skills(extracted)

    score, tips, progress = score_resume(resume_text)

    pdf_iframe = Markup(show_pdf_iframe(save_path))

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H:%M:%S")

    # Request/env metadata (best-effort)
    sec_token = os.urandom(6).hex()
    ip_add = request.headers.get('X-Forwarded-For', request.remote_addr)
    host_name = os.uname().nodename if hasattr(os, 'uname') else os.getenv('HOSTNAME', 'unknown')
    dev_user = os.getenv('USER') or os.getenv('USERNAME') or 'server'
    os_name_ver = f"{os.name}"

    db = get_db()
    cur = db.cursor()

    insert_sql = (
        "INSERT INTO user_data (sec_token, ip_add, host_name, dev_user, os_name_ver, latlong, city, state, country, "
        "act_name, act_mail, act_mob, Name, Email_ID, resume_score, Timestamp, Page_no, Predicted_Field, User_level, "
        "Actual_skills, Recommended_skills, Recommended_courses, pdf_name) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    )

    cur.execute(
        insert_sql,
        (
            sec_token,
            ip_add,
            host_name,
            dev_user,
            os_name_ver,
            None,  # latlong best-effort omitted
            None,  # city
            None,  # state
            None,  # country
            name,
            email,
            phone,
            extracted.get("name"),
            extracted.get("email"),
            str(score),
            timestamp,
            str(extracted.get("no_of_pages")),
            reco.get("field"),
            cand_level,
            str(extracted.get("skills")),
            str(reco.get("skills", [])),
            str(reco.get("courses")),
            filename,
        ),
    )
    db.commit()

    return render_template(
        "results.html",
        parsed=extracted,
        pdf_iframe=pdf_iframe,
        level_msg=level_msg,
        reco=reco,
        score=score,
        tips=tips,
        progress=progress,
    )


@app.get("/uploads/<path:fname>")
def serve_upload(fname):
    return send_from_directory(UPLOAD_FOLDER, fname)


@app.get("/feedback")
def feedback_page():
    return render_template("feedback.html")


@app.post("/feedback")
def submit_feedback():
    name = request.form.get("name")
    email = request.form.get("email")
    feed_score = int(request.form.get("score", 5))
    comments = request.form.get("comments")
    ts = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO user_feedback (feed_name, feed_email, feed_score, comments, Timestamp) VALUES (%s,%s,%s,%s,%s)",
        (name, email, str(feed_score), comments, ts),
    )
    db.commit()
    flash("Thanks! Your feedback was recorded.")
    return redirect(url_for("feedback_page"))


@app.get("/about")
def about():
    return render_template("about.html")


@app.get("/admin")
def admin_login():
    return render_template("admin_login.html")


@app.post("/admin")
def admin_auth():
    u = request.form.get("username")
    p = request.form.get("password")
    if u == os.getenv("ADMIN_USER", "admin") and p == os.getenv("ADMIN_PASS", "admin@resume-analyzer"):
        return redirect(url_for("admin_dash"))
    flash("Wrong ID & Password Provided")
    return redirect(url_for("admin_login"))


@app.get("/admin/dashboard")
def admin_dash():
    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT COUNT(*) FROM user_data")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT ID, sec_token, ip_add, act_name, act_mail, act_mob, Predicted_Field, Timestamp, Name, Email_ID, resume_score, Page_no, pdf_name, User_level, Actual_skills, Recommended_skills, Recommended_courses, city, state, country, latlong, os_name_ver, host_name, dev_user FROM user_data")
    users = cur.fetchall()

    cur.execute("SELECT * FROM user_feedback")
    feedback = cur.fetchall()

    return render_template("admin_dashboard.html", total_users=total_users, users=users, feedback=feedback)


if __name__ == "__main__":
    app.run(debug=True)
