# import os
# import multiprocessing as mp
# import io
# import spacy
# import pprint
# from spacy.matcher import Matcher
# from . import utils   # make sure utils.py exists in the same folder


# class ResumeParser:
#     def __init__(self, resume, skills_file=None, custom_regex=None):
#         """
#         Resume Parser to extract structured information from resumes.
#         """
#         # Load spaCy model
#         self._nlp_model = spacy.load("en_core_web_sm")
#         # self._nlp_model = spacy.load("en_core_web_trf")
#         self.__skills_file = skills_file
#         self.__custom_regex = custom_regex
#         self.__matcher = Matcher(self._nlp_model.vocab)

#         self.__details = {
#             'name': None,
#             'email': None,
#             'mobile_number': None,
#             'skills': None,
#             'degree': None,
#             'no_of_pages': None,
#         }

#         self.__resume = resume

#         # Handle file type
#         if not isinstance(self.__resume, io.BytesIO):
#             ext = os.path.splitext(self.__resume)[1].split('.')[-1]
#         else:
#             ext = self.__resume.name.split('.')[-1]

#         # Extract raw text from resume file
#         self.__text_raw = utils.extract_text(self.__resume, '.' + ext)
#         self.__text = ' '.join(self.__text_raw.split())

#         # Process with spaCy
#         self.__nlp = self._nlp_model(self.__text)
#         self.__custom_nlp = self._nlp_model(self.__text)   # fallback to same model

#         self.__noun_chunks = list(self.__nlp.noun_chunks)

#         # Populate details
#         self.__get_basic_details()

#     def get_extracted_data(self):
#         """Return extracted structured resume data."""
#         return self.__details

#     def __get_basic_details(self):
#         """Extracts basic details like name, email, phone, skills, degree, pages."""
#         # Custom entities from utils
#         try:
#             cust_ent = utils.extract_entities_wih_custom_model(self.__custom_nlp)
#         except Exception:
#             cust_ent = {}

#         # Extract basic fields
#         name = utils.extract_name(self.__nlp, matcher=self.__matcher)
#         email = utils.extract_email(self.__text)
#         mobile = utils.extract_mobile_number(self.__text, self.__custom_regex)
#         skills = utils.extract_skills(
#             self.__nlp, self.__noun_chunks, self.__skills_file
#         )

#         # Extract education-related entities
#         entities = utils.extract_entity_sections_grad(self.__text_raw)

#         # Fill details dictionary
#         try:
#             self.__details['name'] = cust_ent.get('Name', [None])[0]
#         except Exception:
#             self.__details['name'] = name

#         self.__details['email'] = email
#         self.__details['mobile_number'] = mobile
#         self.__details['skills'] = skills

#         # Pages
#         try:
#             self.__details['no_of_pages'] = utils.get_number_of_pages(self.__resume)
#         except Exception:
#             self.__details['no_of_pages'] = None

#         # Degree
#         try:
#             self.__details['degree'] = cust_ent.get('Degree')
#         except Exception:
#             self.__details['degree'] = None

#         return


# # Wrapper for multiprocessing
# def resume_result_wrapper(resume):
#     parser = ResumeParser(resume)
#     return parser.get_extracted_data()


# if __name__ == '__main__':
#     pool = mp.Pool(mp.cpu_count())

#     resumes = []
#     data = []

#     for root, directories, filenames in os.walk('resumes'):
#         for filename in filenames:
#             file = os.path.join(root, filename)
#             resumes.append(file)

#     results = [
#         pool.apply_async(resume_result_wrapper, args=(x,))
#         for x in resumes
#     ]

#     results = [p.get() for p in results]
#     pprint.pprint(results)






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

        # ensure sentence segmentation exists (trf models often include it already)
        if "sentencizer" not in self._nlp_model.pipe_names:
            self._nlp_model.add_pipe("sentencizer", first=True)

        # Extract raw text and normalize whitespace
        ext = self._detect_ext(self.resume)
        self.raw_text = utils.extract_text(self.resume, ext) or ""
        self.text = " ".join(self.raw_text.split())

        # Process with spaCy (transformer model)
        # Use disable to keep pipeline minimal if needed
        self.doc = self._nlp_model(self.text)

        # noun chunks (may be useful for skills)
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

        # populate
        self._get_basic_details()

    # -----------------------
    # Helpers
    # -----------------------
    def _detect_ext(self, path_or_file) -> Optional[str]:
        # allow passing hint (older code style) or detect from file/BytesIO.name
        if isinstance(path_or_file, io.BytesIO):
            return getattr(path_or_file, "name", None)
        if isinstance(path_or_file, str):
            return os.path.splitext(path_or_file)[1]
        return None

    def _get_person_from_doc(self) -> Optional[str]:
        # 1) Prefer custom model/entities via utils (if available)
        try:
            cust = utils.extract_entities_wih_custom_model(self.doc)
            if cust.get("Name"):
                name = cust["Name"][0]
                if name:
                    return name.strip()
        except Exception:
            pass

        # 2) Use spaCy PERSON entities (transformer model is stronger)
        for ent in self.doc.ents:
            if ent.label_.upper() == "PERSON":
                text = ent.text.strip()
                # simple length filter: accept 1-4 token names
                if 1 <= len(text.split()) <= 4:
                    return text

        # 3) Fallback: first non-empty line heuristics (common in resumes)
        for line in (ln.strip() for ln in self.raw_text.splitlines()):
            if not line:
                continue
            # ignore lines that look like emails/phones/addresses by quick checks
            if "@" in line or any(ch.isdigit() for ch in line) and len(line) < 30:
                # but sometimes name contains digits? rarely. skip lines with @
                if "@" in line:
                    continue
            # take first short-ish line as name
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

    # -----------------------
    # Public
    # -----------------------
    def get_extracted_data(self) -> Dict[str, Any]:
        """
        Return the details dictionary (name, email, mobile_number, skills, degree, no_of_pages, raw_text)
        """
        return self.details


# -----------------------
# Simple CLI / test usage
# -----------------------
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
