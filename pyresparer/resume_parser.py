
import os
import io
import spacy
from spacy.language import Language
from spacy.pipeline import Sentencizer
from typing import Optional, Dict, Any
from . import utils

class ResumeParser:
    """
    Minimal, robust resume parser using spaCy transformer model (en_core_web_trf).

    Input:
      - resume: path (str) or io.BytesIO containing the resume file
      - skills_file: optional path to newline-separated skill list
      - custom_regex: optional custom regex for phone numbers

    Output (get_extracted_data):
      dict with keys: name, email, mobile_number, skills, degree, no_of_pages, raw_text
    """

    def __init__(self, resume: Any, skills_file: Optional[str] = None, custom_regex: Optional[str] = None):
        self.resume = resume
        self.skills_file = skills_file
        self.custom_regex = custom_regex

        try:
            self._nlp_model: Language = spacy.load("en_core_web_trf")
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'en_core_web_trf' not found. "
                "Install it with: python -m spacy download en_core_web_trf"
            ) from exc

        if "sentencizer" not in self._nlp_model.pipe_names:
            self._nlp_model.add_pipe("sentencizer", first=True)

        ext = self._detect_ext(self.resume)
        self.raw_text = utils.extract_text(self.resume, ext) or ""
        self.text = " ".join(self.raw_text.split())

        self.doc = self._nlp_model(self.text)

        self.noun_chunks = list(self.doc.noun_chunks)

        self.details: Dict[str, Any] = {
            "name": None,
            "email": None,
            "mobile_number": None,
            "skills": [],
            "degree": None,
            "no_of_pages": None,
            "raw_text": self.raw_text,
        }

        self._get_basic_details()


    def _detect_ext(self, path_or_file) -> Optional[str]:
        if isinstance(path_or_file, io.BytesIO):
            return getattr(path_or_file, "name", None)
        if isinstance(path_or_file, str):
            return os.path.splitext(path_or_file)[1]
        return None

    def _get_person_from_doc(self) -> Optional[str]:
        try:
            cust = utils.extract_entities_wih_custom_model(self.doc)
            if cust.get("Name"):
                name = cust["Name"][0]
                if name:
                    return name.strip()
        except Exception:
            pass

        for ent in self.doc.ents:
            if ent.label_.upper() == "PERSON":
                text = ent.text.strip()
                if 1 <= len(text.split()) <= 4:
                    return text

        for line in (ln.strip() for ln in self.raw_text.splitlines()):
            if not line:
                continue

            if "@" in line or any(ch.isdigit() for ch in line) and len(line) < 30:

                if "@" in line:
                    continue
            if 1 <= len(line.split()) <= 6:
                return line
        return None

    def _get_basic_details(self):
        try:
            self.details["name"] = self._get_person_from_doc()
        except Exception:
            self.details["name"] = None

        try:
            self.details["email"] = utils.extract_email(self.text)
        except Exception:
            self.details["email"] = None

        try:
            self.details["mobile_number"] = utils.extract_mobile_number(self.text, self.custom_regex)
        except Exception:
            self.details["mobile_number"] = None

        try:
            skills = utils.extract_skills(self.doc, self.noun_chunks, self.skills_file)
            # Normalize output to list of capitalized tokens or phrases
            self.details["skills"] = [s for s in skills] if skills else []
        except Exception:
            self.details["skills"] = []

        try:
            cust = utils.extract_entities_wih_custom_model(self.doc)
            if "Degree" in cust:
                self.details["degree"] = cust.get("Degree")
            else:
                # fallback: look for degree keywords in raw text (simple)
                degs = utils.extract_entities_wih_custom_model(self.doc).get("Degree")
                self.details["degree"] = degs if degs else None
        except Exception:
            self.details["degree"] = None

        try:
            self.details["no_of_pages"] = utils.get_number_of_pages(self.resume)
        except Exception:
            self.details["no_of_pages"] = None

    def get_extracted_data(self) -> Dict[str, Any]:
        """
        Return the details dictionary (name, email, mobile_number, skills, degree, no_of_pages, raw_text)
        """
        return self.details


if __name__ == "__main__":
    import pprint
    import sys

    if len(sys.argv) < 2:
        print("Usage: python resume_parser.py <resume_file> [skills_file]")
        sys.exit(1)

    resume_path = sys.argv[1]
    skills_path = sys.argv[2] if len(sys.argv) > 2 else None

    parser = ResumeParser(resume_path, skills_file=skills_path)
    pprint.pprint(parser.get_extracted_data())
