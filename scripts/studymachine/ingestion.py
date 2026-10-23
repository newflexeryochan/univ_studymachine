"""Local, bounded material ingestion; no network access or embedded-code execution.

Original IDs are SHA-256 content identities. Archive member identities additionally
include the parent identity and normalized member name, in a separate namespace.
Rejected inputs that cannot be hashed have explicitly path-based ``rejected_`` IDs.
All extracted sections carry stable reference locations. Optional readers are
imported only when needed. ``storage_dir`` must be private and outside this checkout.
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import io
import itertools
import ntpath
import os
from pathlib import Path
import re
import stat
import unicodedata
import zipfile
from xml.etree import ElementTree


# Public limits can be lowered by callers/tests before a run. Bytes are actual
# bytes read, including nested members; archive metadata is also checked up front.
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_TOTAL_INPUT_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 1000
MAX_FILES = 1000
MAX_ARCHIVE_DEPTH = 3  # Includes the outermost ZIP container.
MAX_COMPRESSION_RATIO = 200
MAX_TEXT_CHARS = 2_000_000
MAX_SECTIONS = 10_000
MAX_DOCUMENT_UNITS = 2000
MAX_SPREADSHEET_ROWS = 20_000
MAX_SPREADSHEET_COLUMNS = 256
MAX_SPREADSHEET_CELLS = 1_000_000
LINES_PER_SECTION = 80

CATEGORIES = frozenset({
    "syllabus", "lecture_slides", "textbook", "lecture_notes", "assignment",
    "historical_exam", "official_solution", "student_solution", "answer_key",
    "formula_sheet", "other",
})
_IMAGES = frozenset({"png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff", "webp", "heic", "heif"})
_OOXML = frozenset({"docx", "pptx", "xlsx"})
_HISTORY = re.compile(
    r"기출|족보|중간고사|기말고사|시험지|모의고사|역대시험|지난시험|"
    r"(?<![a-z])(?:past[\s_-]*(?:papers?|exams?)|previous[\s_-]*exams?|"
    r"historical[\s_-]*exams?|exams?|midterms?|finals?)(?![a-z])", re.I,
)
_CATEGORY_CLUES = (
    ("student_solution", r"학생[\s_-]*(?:풀이|해설|답안)|자필[\s_-]*풀이|student[\s_-]*(?:solutions?|answers?)"),
    ("official_solution", r"공식[\s_-]*(?:풀이|해설|답안)|모범[\s_-]*(?:풀이|답안)|해설|풀이|official[\s_-]*solutions?|worked[\s_-]*solutions?|solutions?"),
    ("answer_key", r"정답|답지|답안|answer[\s_-]*keys?|(?<![a-z])answers?(?![a-z])"),
    ("syllabus", r"강의[\s_-]*계획|수업[\s_-]*계획|교과[\s_-]*안내|syllabus|course[\s_-]*(?:outline|plan)"),
    ("formula_sheet", r"공식[\s_-]*(?:모음|정리|집)|수식[\s_-]*정리|요약[\s_-]*공식|formula[\s_-]*(?:sheet|list)|cheat[\s_-]*sheet"),
    ("assignment", r"과제|숙제|연습[\s_-]*문제|assignments?|homework|problem[\s_-]*sets?"),
    ("lecture_slides", r"강의[\s_-]*(?:슬라이드|자료)|수업[\s_-]*자료|slides?|lecture[\s_-]*(?:slides?|decks?)"),
    ("lecture_notes", r"강의[\s_-]*노트|수업[\s_-]*노트|필기|lecture[\s_-]*notes?|notes?"),
    ("textbook", r"교과서|교재|전공서|text[\s_-]*books?|textbook|chapters?"),
)


class _IngestionError(Exception):
    """An expected rejection with a student-facing Korean message."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _warn(source, code, message):
    if code not in source["limitation_codes"]:
        source["limitation_codes"].append(code)
        source["limitations"].append(message)
    if source["status"] == "processed":
        source["status"] = "partial"


def _review(source, message):
    source["multimodal_review_required"] = True
    _warn(source, "multimodal_review_required", message)


def _add(source, location, text):
    """Append text without exceeding per-source section/character ceilings."""
    if not text or not text.strip():
        return True
    remaining = MAX_TEXT_CHARS - source["character_count"]
    if remaining <= 0 or len(source["sections"]) >= MAX_SECTIONS:
        _warn(source, "text_limit", "텍스트 추출 한도에 도달하여 나머지 내용을 생략했습니다.")
        return False
    truncated = len(text) > remaining
    if truncated:
        text = text[:remaining]
        _warn(source, "text_limit", "텍스트 추출 한도에 도달하여 나머지 내용을 생략했습니다.")
    source["sections"].append({"location": location, "text": text})
    source["character_count"] += len(text)
    return not truncated


def _category(name):
    name = unicodedata.normalize("NFKC", name)
    # A solutions-only file does not establish that original questions exist.
    for category, pattern in _CATEGORY_CLUES[:3]:
        if re.search(pattern, name, re.I):
            return category
    if _HISTORY.search(name):
        return "historical_exam"
    for category, pattern in _CATEGORY_CLUES[3:]:
        if re.search(pattern, name, re.I):
            return category
    return "other"


def _key(path):
    return unicodedata.normalize("NFC", os.fspath(path)).replace("\\", "/").casefold()


def _is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _safe_components(path):
    for component in (path, *path.parents):
        try:
            if _is_link(component.lstat()):
                raise _IngestionError("unsafe_path", "심볼릭 링크 또는 연결 경로는 자료나 보관 경로로 사용할 수 없습니다.")
        except FileNotFoundError:
            continue


def _checkout(path):
    return next((p for p in (path, *path.parents) if (p / ".git").exists()), None)


def _storage_root(storage_dir):
    root = Path(os.path.abspath(os.fspath(storage_dir)))
    try:
        _safe_components(root)
        checkout = _checkout(Path(__file__).absolute().parent)
        if checkout is not None and root.is_relative_to(checkout):
            raise _IngestionError("unsafe_storage", "원본 보관 폴더는 프로그램 소스 폴더 밖의 비공개 경로로 지정해 주세요.")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        originals = root / "originals"
        _safe_components(originals)
        originals.mkdir(mode=0o700, exist_ok=True)
        if not originals.is_dir():
            raise OSError("not a directory")
        return originals
    except _IngestionError as exc:
        raise ValueError(str(exc)) from None
    except (OSError, ValueError):
        raise ValueError("비공개 원본 보관 폴더를 만들거나 사용할 수 없습니다.") from None


def _read_limited(stream, limit):
    chunks = []
    total = 0
    while True:
        chunk = stream.read(min(65536, limit - total + 1))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > limit:
            raise _IngestionError("size_limit", "자료 크기가 허용 한도를 초과하여 읽기를 중단했습니다.")
        chunks.append(chunk)


def _store(originals, data, digest):
    """Create an immutable content copy or verify the existing copy; never replace."""
    target = originals / digest
    _safe_components(originals)
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    except FileExistsError:
        info = target.lstat()
        if _is_link(info) or not stat.S_ISREG(info.st_mode) or info.st_size != len(data):
            raise _IngestionError("storage_conflict", "기존 보관 파일이 원본과 달라 덮어쓰지 않았습니다.")
        with open(target, "rb") as existing:
            opened = os.fstat(existing.fileno())
            if (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
                raise _IngestionError("storage_conflict", "보관 경로가 변경되어 읽기를 중단했습니다.")
            if hashlib.sha256(_read_limited(existing, len(data))).hexdigest() != digest:
                raise _IngestionError("storage_conflict", "기존 보관 파일이 원본과 달라 덮어쓰지 않았습니다.")
    else:
        # A write error deliberately leaves a detectable conflict, never a false copy.
        with os.fdopen(descriptor, "wb") as saved:
            saved.write(data)
    return str(target)


def _member_name(info):
    raw = getattr(info, "orig_filename", info.filename)
    name = unicodedata.normalize("NFC", raw.replace("\\", "/"))
    parts = name.rstrip("/").split("/")
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
    if (not name or name.startswith("/") or ntpath.splitdrive(name)[0]
            or any(not p or p in {".", ".."} or p.endswith((".", " "))
                   or any(ord(c) < 32 or c in ':<>"|?*!' for c in p)
                   or p.split(".")[0].casefold() in reserved for p in parts)):
        raise _IngestionError("unsafe_archive_path", "압축 파일에 안전하지 않은 경로가 있어 내부 자료를 읽지 않았습니다.")
    kind = stat.S_IFMT(info.external_attr >> 16)
    if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or info.external_attr & 0x400:
        raise _IngestionError("archive_link", "압축 파일에 링크 또는 특수 파일이 있어 내부 자료를 읽지 않았습니다.")
    return name.rstrip("/")


def _archive_entries(archive, remaining_files=None):
    entries = archive.infolist()
    if len(entries) > MAX_ARCHIVE_MEMBERS:
        raise _IngestionError("archive_file_limit", "압축 파일의 항목 수가 허용 한도를 초과했습니다.")
    total = 0
    names = set()
    files = []
    for info in entries:
        name = _member_name(info)
        if name.casefold() in names:
            raise _IngestionError("archive_duplicate_path", "압축 파일에 중복되거나 구분할 수 없는 경로가 있어 읽지 않았습니다.")
        names.add(name.casefold())
        if info.is_dir():
            continue
        if info.file_size > MAX_INPUT_BYTES or info.file_size < 0:
            raise _IngestionError("archive_size_limit", "압축 내부 자료의 크기가 허용 한도를 초과했습니다.")
        total += info.file_size
        if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise _IngestionError("archive_size_limit", "압축 해제 시 전체 크기가 허용 한도를 초과합니다.")
        if info.file_size / max(1, info.compress_size) > MAX_COMPRESSION_RATIO:
            raise _IngestionError("archive_ratio_limit", "압축률이 과도하여 압축 폭탄 위험이 있는 자료를 읽지 않았습니다.")
        files.append((info, name))
    if remaining_files is not None and len(files) > remaining_files:
        raise _IngestionError("file_limit", "한 번에 처리할 수 있는 자료 수를 초과했습니다.")
    return files


def _check_ooxml(data, file_type):
    """Apply ZIP limits before a third-party parser and reject XML declarations.

    No DTD/entity expansion is needed for Office material. Cached spreadsheet
    results are inspected without evaluating formulas or opening external links.
    """
    formulas = uncached = 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = _archive_entries(archive)
        for info, name in entries:
            if info.flag_bits & 1:
                raise _IngestionError("encrypted", "암호화된 문서는 잠금을 해제한 사본을 제공해 주세요.")
            if not name.lower().endswith((".xml", ".rels")):
                continue
            with archive.open(info) as stream:
                xml = _read_limited(stream, MAX_INPUT_BYTES)
            if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", xml.replace(b"\x00", b""), re.I):
                raise _IngestionError("unsafe_xml", "외부 선언 또는 엔터티가 포함된 문서는 안전하게 읽을 수 없습니다.")
            if file_type == "xlsx" and name.startswith("xl/worksheets/") and name.endswith(".xml"):
                for _, element in ElementTree.iterparse(io.BytesIO(xml), events=("end",)):
                    if element.tag.rsplit("}", 1)[-1] == "c":
                        children = {child.tag.rsplit("}", 1)[-1]: child for child in element}
                        if "f" in children:
                            formulas += 1
                            if "v" not in children or children["v"].text is None:
                                uncached += 1
                        element.clear()
    return formulas, uncached


def _dependency(module, package, label):
    try:
        return importlib.import_module(module)
    except ImportError:
        raise _IngestionError("missing_dependency", f"{label} 자료를 읽으려면 {package} 패키지를 설치해 주세요. 원본은 비공개 보관 폴더에 보존했습니다.") from None


def _decode(source, data):
    if data.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        encodings = ("utf-32",)
    elif data.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings = ("utf-16",)
    else:
        encodings = ("utf-8-sig", "cp949")
    for encoding in encodings:
        try:
            text = data.decode(encoding)
            if "\x00" in text:
                raise _IngestionError("binary_text", "텍스트 자료에 이진 데이터가 포함되어 읽을 수 없습니다.")
            source["encoding"] = encoding
            return text
        except UnicodeError:
            continue
    _warn(source, "encoding_loss", "문자 인코딩을 확인할 수 없어 일부 문자를 대체했습니다. 원본과 대조해 주세요.")
    source["encoding"] = "utf-8-replacement"
    return data.decode("utf-8", errors="replace")


def _text(source, data):
    text = _decode(source, data)
    # Bound allocation for tiny-line files as well as extracted characters.
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]
        _warn(source, "text_limit", "텍스트 추출 한도에 도달하여 나머지 내용을 생략했습니다.")
    lines = text.splitlines()
    for start in range(0, len(lines), LINES_PER_SECTION):
        if not _add(source, f"lines:{start + 1}-{min(start + LINES_PER_SECTION, len(lines))}", "\n".join(lines[start:start + LINES_PER_SECTION])):
            break


def _csv(source, data):
    reader = csv.reader(io.StringIO(_decode(source, data), newline=""), strict=True)
    rows = []
    start = 1
    try:
        for number, row in enumerate(reader, 1):
            if number > MAX_SPREADSHEET_ROWS:
                _warn(source, "row_limit", "표의 행 수가 허용 한도를 초과하여 나머지 행을 생략했습니다.")
                break
            if len(row) > MAX_SPREADSHEET_COLUMNS:
                row = row[:MAX_SPREADSHEET_COLUMNS]
                _warn(source, "column_limit", "표의 열 수가 허용 한도를 초과하여 나머지 열을 생략했습니다.")
            rows.append("\t".join(row))
            if len(rows) == LINES_PER_SECTION:
                if not _add(source, f"rows:{start}-{number}", "\n".join(rows)):
                    return
                rows = []
                start = number + 1
    finally:
        if rows:
            _add(source, f"rows:{start}-{start + len(rows) - 1}", "\n".join(rows))


def _pdf(source, data):
    pypdf = _dependency("pypdf", "pypdf", "PDF")
    document = pypdf.PdfReader(io.BytesIO(data))
    if document.is_encrypted and not document.decrypt(""):
        raise _IngestionError("encrypted", "암호화된 PDF는 잠금을 해제한 사본을 제공해 주세요.")
    source["page_count"] = len(document.pages)
    if source["page_count"] > MAX_DOCUMENT_UNITS:
        _warn(source, "unit_limit", "문서의 페이지 수가 허용 한도를 초과하여 일부만 읽었습니다.")
    for number, page in enumerate(itertools.islice(document.pages, MAX_DOCUMENT_UNITS), 1):
        try:
            text = page.extract_text() or ""
            resources = page.get("/Resources", {})
            resources = resources.get_object() if hasattr(resources, "get_object") else resources
            objects = resources.get("/XObject", {})
            objects = objects.get_object() if hasattr(objects, "get_object") else objects
            has_images = any(obj.get_object().get("/Subtype") == "/Image" for obj in objects.values())
            if has_images or not text.strip():
                _review(source, "PDF의 이미지 또는 스캔·빈 페이지는 텍스트만으로 판독할 수 없어 멀티모달 검토가 필요합니다.")
            if not _add(source, f"page:{number}", text):
                break
        except Exception:
            _warn(source, "page_read_error", "일부 PDF 페이지를 읽을 수 없습니다. 원본을 확인해 주세요.")


def _pptx(source, data):
    module = _dependency("pptx", "python-pptx", "PPTX")
    presentation = module.Presentation(io.BytesIO(data))
    source["page_count"] = len(presentation.slides)
    if source["page_count"] > MAX_DOCUMENT_UNITS:
        _warn(source, "unit_limit", "슬라이드 수가 허용 한도를 초과하여 일부만 읽었습니다.")
    for number, slide in enumerate(itertools.islice(presentation.slides, MAX_DOCUMENT_UNITS), 1):
        texts = []
        seen = 0
        stack = [iter(slide.shapes)]
        while stack:
            shape = next(stack[-1], None)
            if shape is None:
                stack.pop()
                continue
            seen += 1
            if seen > MAX_SECTIONS:
                _warn(source, "shape_limit", "슬라이드의 개체 수가 허용 한도를 초과하여 일부를 생략했습니다.")
                break
            if getattr(shape, "has_text_frame", False):
                texts.append(shape.text)
            if getattr(shape, "has_table", False):
                texts.extend("\t".join(cell.text for cell in row.cells) for row in shape.table.rows)
            if getattr(shape, "shape_type", None) in (7, 11, 13, 16) or getattr(shape, "has_chart", False):
                _review(source, "슬라이드의 그림·차트·삽입 개체는 멀티모달 검토가 필요합니다. 삽입된 프로그램은 실행하지 않았습니다.")
            if getattr(shape, "shape_type", None) == 6:
                stack.append(iter(shape.shapes))
        text = "\n".join(texts)
        if not text.strip():
            _review(source, "텍스트가 없는 슬라이드는 멀티모달 검토가 필요합니다.")
        if not _add(source, f"slide:{number}", text):
            break
        if getattr(slide, "has_notes_slide", False):
            notes = slide.notes_slide.notes_text_frame
            if notes is not None and not _add(source, f"slide:{number}:notes", notes.text):
                break


def _docx(source, data):
    module = _dependency("docx", "python-docx", "DOCX")
    document = module.Document(io.BytesIO(data))
    paragraph_type = importlib.import_module("docx.text.paragraph").Paragraph
    table_type = importlib.import_module("docx.table").Table
    paragraphs = tables = units = 0
    for element in document.element.body:
        kind = element.tag.rsplit("}", 1)[-1]
        if kind not in {"p", "tbl"}:
            continue
        units += 1
        if units > MAX_DOCUMENT_UNITS:
            _warn(source, "unit_limit", "문단·표 수가 허용 한도를 초과하여 일부만 읽었습니다.")
            break
        if kind == "p":
            paragraphs += 1
            if not _add(source, f"paragraph:{paragraphs}", paragraph_type(element, document).text):
                break
        else:
            tables += 1
            table = table_type(element, document)
            rows = []
            number = 0
            for number, row in enumerate(table.rows, 1):
                if number > MAX_SPREADSHEET_ROWS:
                    _warn(source, "row_limit", "표의 행 수가 허용 한도를 초과하여 나머지 행을 생략했습니다.")
                    break
                cells = list(itertools.islice(row.cells, MAX_SPREADSHEET_COLUMNS + 1))
                if len(cells) > MAX_SPREADSHEET_COLUMNS:
                    _warn(source, "column_limit", "표의 열 수가 허용 한도를 초과하여 나머지 열을 생략했습니다.")
                rows.append("\t".join(c.text for c in cells[:MAX_SPREADSHEET_COLUMNS]))
                if len(rows) == LINES_PER_SECTION:
                    if not _add(source, f"table:{tables}:rows:{number - len(rows) + 1}-{number}", "\n".join(rows)):
                        return
                    rows = []
            end = min(number, MAX_SPREADSHEET_ROWS)
            if rows and not _add(source, f"table:{tables}:rows:{end - len(rows) + 1}-{end}", "\n".join(rows)):
                break
    if document.inline_shapes or document.element.xpath(".//w:pict | .//w:object"):
        _review(source, "문서의 그림·삽입 개체는 멀티모달 검토가 필요합니다. 삽입된 프로그램은 실행하지 않았습니다.")
    if any(any(p.text for p in s.header.paragraphs + s.footer.paragraphs) for s in document.sections):
        _warn(source, "header_footer", "머리글·바닥글은 본문 추출에 포함하지 않았습니다. 원본을 확인해 주세요.")


def _xlsx(source, data, formula_counts):
    module = _dependency("openpyxl", "openpyxl", "XLSX")
    source["formula_count"], source["uncached_formula_count"] = formula_counts
    if source["uncached_formula_count"]:
        _warn(source, "uncached_formulas", "저장된 계산 결과가 없는 수식 셀이 있습니다. 수식을 실행하지 않아 해당 값은 비어 있을 수 있습니다.")
    workbook = module.load_workbook(io.BytesIO(data), read_only=True, data_only=True, keep_links=False)
    try:
        cells_read = 0
        if len(workbook.worksheets) > MAX_DOCUMENT_UNITS:
            _warn(source, "unit_limit", "시트 수가 허용 한도를 초과하여 일부만 읽었습니다.")
        for index, sheet in enumerate(workbook.worksheets[:MAX_DOCUMENT_UNITS], 1):
            max_row = min(sheet.max_row or MAX_SPREADSHEET_ROWS, MAX_SPREADSHEET_ROWS)
            max_col = min(sheet.max_column or MAX_SPREADSHEET_COLUMNS, MAX_SPREADSHEET_COLUMNS)
            if (sheet.max_row or 0) > MAX_SPREADSHEET_ROWS:
                _warn(source, "row_limit", "시트의 행 수가 허용 한도를 초과하여 나머지 행을 생략했습니다.")
            if (sheet.max_column or 0) > MAX_SPREADSHEET_COLUMNS:
                _warn(source, "column_limit", "시트의 열 수가 허용 한도를 초과하여 나머지 열을 생략했습니다.")
            rows = []
            start = 1
            for number, row in enumerate(sheet.iter_rows(max_row=max_row, max_col=max_col, values_only=True), 1):
                cells_read += len(row)
                if cells_read > MAX_SPREADSHEET_CELLS:
                    if any(r.strip() for r in rows):
                        _add(source, f"sheet:{index}:rows:{start}-{number - 1}", f"[{sheet.title}]\n" + "\n".join(rows))
                    _warn(source, "cell_limit", "스프레드시트의 셀 수가 허용 한도를 초과하여 나머지를 생략했습니다.")
                    return
                rows.append("\t".join("" if value is None else str(value) for value in row))
                if len(rows) == LINES_PER_SECTION:
                    if any(r.strip() for r in rows) and not _add(source, f"sheet:{index}:rows:{start}-{number}", f"[{sheet.title}]\n" + "\n".join(rows)):
                        return
                    rows = []
                    start = number + 1
            if any(r.strip() for r in rows) and not _add(source, f"sheet:{index}:rows:{start}-{start + len(rows) - 1}", f"[{sheet.title}]\n" + "\n".join(rows)):
                return
    finally:
        workbook.close()


class _Run:
    def __init__(self, originals, overrides):
        self.originals = originals
        self.overrides = {_key(k): v for k, v in overrides.items()}
        self.sources = []
        self.by_id = {}
        self.bytes_read = 0
        self.file_count = 0

    def source(self, filename, original_path, digest=None, parent=None, member=None):
        if digest is None:
            identity = "rejected_" + hashlib.sha256(original_path.encode("utf-8", errors="surrogatepass")).hexdigest()
        elif parent is None:
            identity = "src_" + digest
        else:
            qualified = f"{parent['id']}\x00{member}\x00{digest}"
            identity = "member_" + hashlib.sha256(qualified.encode("utf-8")).hexdigest()
        detected = _category(filename.rsplit("!/", 1)[-1])
        override = next((self.overrides[k] for k in (_key(original_path), _key(filename), _key(filename.rsplit("!/", 1)[-1].rsplit("/", 1)[-1])) if k in self.overrides), None)
        category = override or detected
        suspected = category == "historical_exam" or (
            override is None and category not in {"official_solution", "student_solution", "answer_key"}
            and bool(parent and parent["suspected_history"]))
        source = {
            "id": identity, "filename": filename, "original_path": original_path,
            "sha256": digest, "file_type": Path(filename).suffix.lower().lstrip(".") or "unknown",
            "category": category, "status": "processed", "sections": [], "page_count": 0,
            "limitations": [], "limitation_codes": [], "topic_ids": [], "question_ids": [],
            "storage_path": None, "section_count": 0, "character_count": 0,
            "limitation_count": 0, "multimodal_review_required": False,
            "suspected_history": suspected, "unreadable_history": False,
            "category_overridden": override is not None,
            "archive_parent_id": parent["id"] if parent else None,
            "aliases": [{"filename": filename, "original_path": original_path}],
        }
        if identity in self.by_id:
            existing = self.by_id[identity]
            if source["aliases"][0] not in existing["aliases"]:
                existing["aliases"].extend(source["aliases"])
            if suspected:
                existing["suspected_history"] = True
                existing["category"] = "historical_exam"
            elif existing["category"] == "other":
                existing["category"] = category
            return existing, False
        self.by_id[identity] = source
        self.sources.append(source)
        return source, True

    def reject(self, filename, path, code, message, parent=None):
        source, _ = self.source(filename, path, parent=parent)
        _warn(source, code, message)
        source["status"] = "failed"
        return source

    def read(self, stream):
        remaining = MAX_TOTAL_INPUT_BYTES - self.bytes_read
        if remaining <= 0:
            raise _IngestionError("total_size_limit", "이번 작업의 전체 자료 크기가 허용 한도에 도달했습니다.")
        try:
            data = _read_limited(stream, min(MAX_INPUT_BYTES, remaining))
        except _IngestionError:
            # Charge the entire permitted read, even if it was rejected.
            self.bytes_read += min(MAX_INPUT_BYTES, remaining)
            raise
        self.bytes_read += len(data)
        return data

    def process(self, data, filename, path, parent=None, member=None, depth=0):
        digest = hashlib.sha256(data).hexdigest()
        source, fresh = self.source(filename, path, digest, parent, member)
        if not fresh:
            return source
        try:
            source["storage_path"] = _store(self.originals, data, digest)
            kind = source["file_type"]
            if kind == "zip":
                self.archive(source, data, depth)
            elif kind in {"txt", "md", "markdown", "csv"}:
                (_csv if kind == "csv" else _text)(source, data)
            elif kind == "pdf":
                _pdf(source, data)
            elif kind in _OOXML:
                counts = _check_ooxml(data, kind)
                if kind == "xlsx":
                    _xlsx(source, data, counts)
                else:
                    (_docx if kind == "docx" else _pptx)(source, data)
            elif kind in _IMAGES:
                _review(source, "이미지 자료는 텍스트를 추출하지 않았습니다. 멀티모달 검토가 필요합니다.")
            elif kind in {"doc", "ppt", "xls"}:
                raise _IngestionError("legacy_format", "이전 형식의 문서는 자동으로 읽을 수 없습니다. DOC는 DOCX, PPT는 PPTX, XLS는 XLSX 또는 PDF로 변환한 사본을 제공해 주세요.")
            else:
                raise _IngestionError("unsupported_format", "지원하지 않는 자료 형식입니다. TXT, MD, CSV, PDF, PPTX, DOCX, XLSX 또는 이미지 사본을 제공해 주세요.")
            if not source["sections"] and kind != "zip" and not source["limitations"]:
                _warn(source, "empty_content", "추출할 수 있는 텍스트가 없습니다. 원본을 확인해 주세요.")
        except _IngestionError as exc:
            _warn(source, exc.code, str(exc))
            source["status"] = "partial" if source["sections"] else "failed"
        except Exception:
            _warn(source, "read_error", "자료가 손상되었거나 내용을 읽을 수 없습니다. 원본 또는 변환한 사본을 확인해 주세요.")
            source["status"] = "partial" if source["sections"] else "failed"
        return source

    def archive(self, source, data, depth):
        if depth >= MAX_ARCHIVE_DEPTH:
            raise _IngestionError("archive_depth_limit", "압축 파일의 중첩 깊이가 허용 한도를 초과했습니다.")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            # Inspect labels before safety rejection as even an unreadable archive
            # can establish suspected history. Explicit host corrections still win.
            if (not source["category_overridden"]
                    and any(_category(i.filename) == "historical_exam" for i in archive.infolist())):
                source["suspected_history"] = True
            entries = _archive_entries(archive, MAX_FILES - self.file_count)
            if not entries:
                raise _IngestionError("empty_archive", "압축 파일 안에 처리할 자료가 없습니다.")
            children = []
            for info, name in entries:
                filename = f"{source['filename']}!/{name}"
                path = f"{source['original_path']}!/{name}"
                if self.file_count >= MAX_FILES:
                    _warn(source, "file_limit", "한 번에 처리할 수 있는 자료 수를 초과하여 나머지를 생략했습니다.")
                    break
                self.file_count += 1
                try:
                    if info.flag_bits & 1:
                        raise _IngestionError("encrypted", "암호화된 압축 내부 자료는 잠금을 해제한 사본을 제공해 주세요.")
                    with archive.open(info) as stream:
                        content = self.read(stream)
                    child = self.process(content, filename, path, source, name, depth + 1)
                except _IngestionError as exc:
                    child = self.reject(filename, path, exc.code, str(exc), source)
                except Exception:
                    child = self.reject(filename, path, "archive_member_error", "압축 내부 자료가 손상되었거나 읽을 수 없습니다.", source)
                children.append(child)
            if any(c["status"] != "processed" for c in children) or len(children) != len(entries):
                _warn(source, "incomplete_archive", "압축 내부 자료 일부를 완전히 읽지 못했습니다. 각 자료의 제한 사항을 확인해 주세요.")
                if children and all(c["status"] == "failed" for c in children):
                    source["status"] = "failed"


def ingest(paths, storage_dir, category_overrides=None):
    """Return a JSON-serializable v1 source manifest, preserving admitted originals.

    ``paths`` is a file path or an iterable of file paths (directories/links are
    rejected). Overrides map absolute/relative paths, archive-qualified names, or
    basenames to contract categories; path matches win. Repeated identical input
    content is represented once with aliases. Explicit host categories take
    precedence over filename guesses. Unreadable suspected history is classified
    as ``historical_exam``; solution-only filenames do not establish history.

    Additional per-source fields expose storage, aliases, review flags and counts.
    A top-level ``counts`` summarizes outcomes. Configuration/storage errors raise
    ValueError; individual bad inputs become failed records, never stop the batch.
    """
    overrides = category_overrides if category_overrides is not None else {}
    if not hasattr(overrides, "items") or any(v not in CATEGORIES for v in overrides.values()):
        raise ValueError("자료 분류 지정은 지원되는 분류 이름으로 된 경로·파일명 사전이어야 합니다.")
    normalized = {}
    for key, value in overrides.items():
        normalized[os.fspath(key)] = value
        if "!/" not in os.fspath(key):
            normalized[os.path.abspath(os.fspath(key))] = value
    originals = _storage_root(storage_dir)
    run = _Run(originals, normalized)
    if isinstance(paths, (str, os.PathLike)):
        paths = [paths]
    for item in paths:
        path = Path(os.path.abspath(os.fspath(item)))
        if run.file_count >= MAX_FILES:
            run.reject(path.name, str(path), "file_limit", "한 번에 처리할 수 있는 자료 수를 초과하여 나머지 입력을 처리하지 않았습니다.")
            break  # Also bounds generator inputs; no eager unbounded list().
        run.file_count += 1
        try:
            _safe_components(path)
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise _IngestionError("not_regular_file", "일반 파일만 자료로 읽을 수 있습니다. 폴더·장치·링크는 제외해 주세요.")
            if info.st_size > MAX_INPUT_BYTES:
                raise _IngestionError("size_limit", "자료 크기가 파일당 허용 한도를 초과하여 읽지 않았습니다.")
            with open(path, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    raise _IngestionError("unsafe_path", "자료 경로가 변경되어 읽기를 중단했습니다.")
                data = run.read(stream)
            run.process(data, path.name, str(path))
        except _IngestionError as exc:
            run.reject(path.name, str(path), exc.code, str(exc))
        except OSError:
            run.reject(path.name, str(path), "input_read_error", "자료 파일이 없거나 읽기 권한이 없습니다. 경로와 권한을 확인해 주세요.")
    for source in run.sources:
        source["section_count"] = len(source["sections"])
        source["limitation_count"] = len(source["limitations"])
        source["unreadable_history"] = source["suspected_history"] and (
            source["status"] != "processed" or (source["file_type"] != "zip" and not source["sections"]))
        if source["unreadable_history"]:
            source["category"] = "historical_exam"
    counts = {status: sum(s["status"] == status for s in run.sources) for status in ("processed", "partial", "failed")}
    counts.update({
        "total_sources": len(run.sources), "input_bytes": run.bytes_read,
        "sections": sum(s["section_count"] for s in run.sources),
        "limitations": sum(s["limitation_count"] for s in run.sources),
        "archive_members": sum(s["archive_parent_id"] is not None for s in run.sources),
        "multimodal_review_required": sum(s["multimodal_review_required"] for s in run.sources),
    })
    return {"schema_version": 1, "sources": run.sources, "counts": counts}
