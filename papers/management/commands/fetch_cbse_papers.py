"""
Download CBSE previous-year papers from cbse.gov.in into an import_papers folder.

    python manage.py fetch_cbse_papers                 # → papers_import/cbse/<class>/<subject>/<year>.pdf
    python manage.py import_papers papers_import

CBSE publishes one zip per subject per exam holding every regional set (often 50 MB+). Zips are
read over HTTP range requests and only one set (the x-1-1 paper) is downloaded per subject/exam.
Files that already exist in the output folder are skipped, so the command can be re-run.
"""
import io
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from papers.services import recent_exam_years

BASE_URL = "https://www.cbse.gov.in/cbsenew/"
INDEX_URL = BASE_URL + "question-paper.html"
USER_AGENT = "Mozilla/5.0 (PrepAI paper importer)"
LINK_RE = re.compile(r'href="(question-paper/(?P<year>\d{4})(?P<comptt>-COMPTT)?/(?P<cls>[^/"]+)/(?P<file>[^"]+))"',
                     re.IGNORECASE)
CLASS_DIRS = {"x": 10, "second_board_x": 10, "xii": 12}

# Subject slug (see boards/catalog.py) → regex on the file name, lower-cased with everything
# except letters removed (CBSE's names vary every year: "Math_S", "MATHEMATICS_STANDARD", ...).
SUBJECT_PATTERNS = {
    10: {
        "english": r"english(ll|.*lit.*)|englishlanlit",
        "hindi-course-a": r"hindi(cour+s+e)?a(upd)?",
        "hindi-course-b": r"hindi(cour+s+e)?b(upd)?",
        "mathematics": r"(math|maths|mathematics|mathmatics)(s|std|standard)",
        "mathematics-basic": r"(math|maths|mathematics|mathmatics)(b|basic)",
        "science": r"scie?nce",
        "social-science": r"socialscience|sst",
        "sanskrit": r"sanskrit",
        "computer-applications": r"computerapplications?",
        "information-technology": r"informationtechnology",
        "artificial-intelligence": r"artificialintel.*",
    },
    12: {
        "english-core": r"(english|eng)core",
        "hindi-core": r"hindicore",
        "physics": r"physics",
        "chemistry": r"chemistry",
        "biology": r"biology",
        "mathematics": r"math|maths|mathematics",
        "applied-mathematics": r"appliedmath(s|ematics)?",
        "accountancy": r"accountancy",
        "business-studies": r"businessstudies|bs",
        "economics": r"economics",
        "history": r"history",
        "geography": r"geography",
        "political-science": r"pol(i?ti?cal)?science",
        "psychology": r"psychology",
        "sociology": r"sociology",
        "computer-science": r"computerscience",
        "informatics-practices": r"informatics?practices",
        "physical-education": r"physicaleducation|phyedu",
    },
}
SKIP_SET_RE = re.compile(r"visual|blind|\bvi\b|[_ ]vi[_ .]|\d+\s*b[_ ]", re.IGNORECASE)
FIRST_SET_RE = re.compile(r"(?<!\d)\d+[A-Z]?[-_ ]1[-_ ]1(?!\d)", re.IGNORECASE)


def _get(url, byte_range=None, attempts=4):
    headers = {"User-Agent": USER_AGENT}
    if byte_range:
        headers["Range"] = "bytes=%d-%d" % byte_range
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as resp:
                return resp.read(), resp.headers
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == attempts - 1 or getattr(exc, "code", 500) == 404:
                raise
            time.sleep(2 ** attempt)


class RemoteFile(io.RawIOBase):
    """Seekable read-only file over HTTP range requests, enough for zipfile.ZipFile."""

    BLOCK = 256 * 1024

    def __init__(self, url):
        self.url, self.pos = url, 0
        _, headers = _get(url, (0, 0))
        self.size = int(headers["Content-Range"].rsplit("/", 1)[1])
        self.buf_start, self.buf = 0, b""

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        self.pos = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence] + offset
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        end = self.pos + n
        if not (self.buf_start <= self.pos and end <= self.buf_start + len(self.buf)):
            fetch_end = min(self.size, self.pos + max(n, self.BLOCK)) - 1
            self.buf, _ = _get(self.url, (self.pos, fetch_end))
            self.buf_start = self.pos
        data = self.buf[self.pos - self.buf_start:end - self.buf_start]
        self.pos += len(data)
        return data


def _letters(name):
    return re.sub(r"[^a-z]", "", name.casefold())


def match_subject(class_number, filename):
    stem = _letters(Path(filename).stem)
    for slug, pattern in SUBJECT_PATTERNS[class_number].items():
        if re.fullmatch(pattern, stem):
            return slug
    return None


def pick_set(names, subject_slug):
    """Choose one paper from a zip's member names: the x-1-1 set, never the visually-impaired one."""
    pdfs = [n for n in names if n.lower().endswith(".pdf") and not SKIP_SET_RE.search(Path(n).name)]
    if "hindi" not in subject_slug:
        english = [n for n in pdfs if not re.search(r"hindi\s*med", n, re.IGNORECASE)]
        pdfs = english or pdfs
    if not pdfs:
        return None
    first = [n for n in pdfs if FIRST_SET_RE.search(Path(n).name)]
    natural = lambda n: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", n)]  # noqa: E731
    return sorted(first or pdfs, key=natural)[0]


class Command(BaseCommand):
    help = "Download CBSE previous-year papers (one set per subject/exam) into an import_papers folder"

    def add_arguments(self, parser):
        parser.add_argument("--out", default="papers_import", help="Output folder (default: papers_import)")
        parser.add_argument("--years", nargs="*", type=int, help="Exam years (default: last five)")
        parser.add_argument("--dry-run", action="store_true", help="List what would be downloaded.")

    def handle(self, *args, **options):
        years = set(options["years"] or recent_exam_years())
        out = Path(options["out"]) / "cbse"
        try:
            html, _ = _get(INDEX_URL)
        except urllib.error.URLError as exc:
            raise CommandError(f"Could not load {INDEX_URL}: {exc}")

        jobs = {}
        for m in LINK_RE.finditer(html.decode("utf-8", "replace")):
            year, cls = int(m["year"]), CLASS_DIRS.get(m["cls"].lower())
            if year not in years or cls is None:
                continue
            slug = match_subject(cls, m["file"].strip())
            if not slug:
                continue
            name = f"{year}-supplementary.pdf" if m["comptt"] else f"{year}.pdf"
            jobs.setdefault(out / str(cls) / slug / name, m[1].strip())

        stats = {"downloaded": 0, "existing": 0, "failed": 0}
        for target, href in sorted(jobs.items()):
            if target.exists():
                stats["existing"] += 1
                continue
            url = BASE_URL + urllib.parse.quote(href, safe="/")
            if options["dry_run"]:
                self.stdout.write(f"{target} <- {href}")
                continue
            try:
                data, source = self._fetch(url, target.parent.name)
            except Exception as exc:  # noqa: BLE001 — report and carry on with the other papers
                stats["failed"] += 1
                self.stderr.write(self.style.WARNING(f"fail {href}: {exc}"))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            stats["downloaded"] += 1
            self.stdout.write(f"{target} <- {href}{f' :: {source}' if source else ''}")

        self.stdout.write(self.style.SUCCESS(", ".join(f"{v} {k}" for k, v in stats.items())))
        self._report_gaps(out, years)

    def _fetch(self, url, subject_slug):
        lower = url.lower()
        if lower.endswith(".pdf"):
            data, _ = _get(url)
            source = ""
        elif lower.endswith(".zip"):
            with zipfile.ZipFile(RemoteFile(url)) as archive:
                source = pick_set(archive.namelist(), subject_slug)
                if not source:
                    raise ValueError("no usable PDF in zip")
                data = archive.read(source)
        else:
            raise ValueError("unsupported archive type")
        if not data.startswith(b"%PDF"):
            raise ValueError("downloaded file is not a PDF")
        return data, source

    def _report_gaps(self, out, years):
        for cls, patterns in SUBJECT_PATTERNS.items():
            for slug in patterns:
                missing = [str(y) for y in sorted(years) if not (out / str(cls) / slug / f"{y}.pdf").exists()]
                if missing:
                    self.stdout.write(f"  no main-exam paper: class {cls} {slug} {', '.join(missing)}")
