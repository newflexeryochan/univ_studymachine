"""Synthetic-only format, failure, policy-metadata and security regression tests."""

import base64
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import warnings
import zipfile

import pytest

from studymachine import ingestion as ing


def material(tmp_path, name="notes.txt", data=b"A useful source\nSecond line"):
    path = tmp_path / "inputs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def run(tmp_path, paths, overrides=None):
    return ing.ingest(paths, tmp_path / "private", overrides)


def one(tmp_path, path, overrides=None):
    return run(tmp_path, [path], overrides)["sources"][0]


def zipped(entries, compression=zipfile.ZIP_STORED):
    output = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(output, "w", compression=compression) as archive:
            for name, content in entries:
                info = name if isinstance(name, zipfile.ZipInfo) else zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
                info.compress_type = compression
                archive.writestr(info, content)
    return output.getvalue()


def pdf_bytes(text=b"Evidence in a PDF", image=False):
    """Build a small real PDF with xref offsets, without needing a PDF writer."""
    stream = b"BT /F1 12 Tf 20 100 Td (" + text + b") Tj ET" if text else b""
    resources = b"/Font << /F1 4 0 R >>" + (b" /XObject << /Im1 6 0 R >>" if image else b"")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << " + resources + b" >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    if image:
        objects.append(b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Length 3 >>\nstream\n\xff\x00\x00\nendstream")
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, value in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + value + b"\nendobj\n")
    start = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode())
    return bytes(output)


def test_manifest_identity_references_copies_and_counts(tmp_path):
    data = "첫째 줄\n둘째 줄".encode()
    path = material(tmp_path, "강의노트.txt", data)
    manifest = run(tmp_path, [path])
    source = manifest["sources"][0]
    assert manifest["schema_version"] == 1
    assert source["sha256"] == hashlib.sha256(data).hexdigest()
    assert source["id"] == "src_" + source["sha256"]
    assert source["status"] == "processed"
    assert source["category"] == "lecture_notes"
    assert source["sections"] == [{"location": "lines:1-2", "text": "첫째 줄\n둘째 줄"}]
    assert source["topic_ids"] == source["question_ids"] == []
    assert Path(source["storage_path"]).is_absolute()
    assert Path(source["storage_path"]).read_bytes() == path.read_bytes() == data
    assert source["section_count"] == 1
    assert source["character_count"] == len("첫째 줄\n둘째 줄")
    assert source["limitation_count"] == 0
    assert manifest["counts"]["processed"] == 1
    assert manifest["counts"]["input_bytes"] == len(data)
    assert json.loads(json.dumps(manifest, ensure_ascii=False)) == manifest


def test_stable_ids_aliases_and_no_original_overwrite(tmp_path):
    first = material(tmp_path, "notes.txt", b"same bytes")
    second = material(tmp_path, "renamed.txt", b"same bytes")
    original = one(tmp_path, first)
    copied = Path(original["storage_path"])
    before = copied.stat().st_mtime_ns
    manifest = run(tmp_path, [second, first, second])
    assert len(manifest["sources"]) == 1
    assert manifest["sources"][0]["id"] == original["id"]
    assert len(manifest["sources"][0]["aliases"]) == 2
    assert copied.stat().st_mtime_ns == before
    assert first.read_bytes() == second.read_bytes() == copied.read_bytes()


def test_modified_content_changes_identity(tmp_path):
    path = material(tmp_path)
    original = one(tmp_path, path)
    path.write_bytes(b"changed")
    changed = one(tmp_path, path)
    assert changed["id"] != original["id"]
    assert Path(original["storage_path"]).read_bytes() != Path(changed["storage_path"]).read_bytes()


@pytest.mark.parametrize(("name", "category"), [
    ("강의계획서.txt", "syllabus"), ("course_outline.txt", "syllabus"),
    ("강의슬라이드.txt", "lecture_slides"), ("lecture-slides.md", "lecture_slides"),
    ("전공교재.txt", "textbook"), ("textbook_chapter_2.txt", "textbook"),
    ("필기.txt", "lecture_notes"), ("lecture_notes.md", "lecture_notes"),
    ("숙제.txt", "assignment"), ("problem_set_2.txt", "assignment"),
    ("2022_기출.txt", "historical_exam"), ("past_exam.txt", "historical_exam"),
    ("2024_midterm.txt", "historical_exam"), ("족보.txt", "historical_exam"),
    ("공식해설.txt", "official_solution"), ("past_exam_solutions.txt", "official_solution"),
    ("기출_공식풀이.txt", "official_solution"), ("final_answer_key.txt", "answer_key"),
    ("기출_정답.txt", "answer_key"), ("past_exam_student_solution.txt", "student_solution"),
    ("학생답안.txt", "student_solution"), ("past_exam_answers.txt", "answer_key"),
    ("formula_sheet.txt", "formula_sheet"),
    ("공식정리.txt", "formula_sheet"), ("reference.txt", "other"),
])
def test_korean_and_english_category_clues(tmp_path, name, category):
    source = one(tmp_path, material(tmp_path, name))
    assert source["category"] == category
    assert source["suspected_history"] == (category == "historical_exam")


@pytest.mark.parametrize(("name", "category"), [
    ("past_exam_solutions.pdf", "official_solution"),
    ("기출_정답.pdf", "answer_key"),
    ("past_exam_student_solution.pdf", "student_solution"),
])
def test_unreadable_solution_only_does_not_establish_history(tmp_path, name, category):
    source = one(tmp_path, material(tmp_path, name, b"malformed document"))
    assert source["status"] == "failed"
    assert source["category"] == category
    assert not source["suspected_history"]
    assert not source["unreadable_history"]


def test_override_path_priority_and_host_correction(tmp_path):
    path = material(tmp_path, "past_exam.pdf", b"invalid PDF")
    source = one(tmp_path, path, {path.name: "historical_exam", path: "lecture_slides"})
    assert source["category"] == "lecture_slides"
    assert source["category_overridden"]
    assert not source["suspected_history"]
    assert not source["unreadable_history"]
    unclear = material(tmp_path, "scan.pdf", b"invalid PDF")
    source = one(tmp_path, unclear, {unclear.name: "historical_exam"})
    assert source["category"] == "historical_exam"
    assert source["suspected_history"] and source["unreadable_history"]


def test_unreadable_and_duplicate_history_fail_closed(tmp_path):
    ordinary = material(tmp_path, "scan.pdf", b"bad PDF")
    history = material(tmp_path, "기출.pdf", b"bad PDF")
    source = run(tmp_path, [ordinary, history])["sources"][0]
    assert source["status"] == "failed"
    assert source["category"] == "historical_exam"
    assert source["suspected_history"] and source["unreadable_history"]


@pytest.mark.parametrize(("name", "data", "expected"), [
    ("notes.MD", b"# Definition\nA formula", "# Definition\nA formula"),
    ("notes.txt", "한글 자료".encode("cp949"), "한글 자료"),
    ("notes.txt", "한글 자료".encode("utf-16"), "한글 자료"),
    ("notes.txt", "한글 자료".encode("utf-32"), "한글 자료"),
    ("notes.txt", b"\xef\xbb\xbfBOM", "BOM"),
])
def test_native_text_encodings(tmp_path, name, data, expected):
    source = one(tmp_path, material(tmp_path, name, data))
    assert source["status"] == "processed"
    assert source["sections"][0]["text"] == expected


def test_encoding_loss_is_partial(tmp_path):
    source = one(tmp_path, material(tmp_path, data=b"text\xff"))
    assert source["status"] == "partial"
    assert "encoding_loss" in source["limitation_codes"]


def test_native_csv_preserves_formula_as_text_and_row_references(tmp_path):
    source = one(tmp_path, material(tmp_path, "table.csv", '이름,값\n"가,나",=1+1\n'.encode()))
    assert source["status"] == "processed"
    assert source["sections"] == [{"location": "rows:1-2", "text": "이름\t값\n가,나\t=1+1"}]


def test_bad_csv_preserves_readable_prefix_as_partial(tmp_path):
    source = one(tmp_path, material(tmp_path, "bad.csv", b'heading,value\n"unterminated'))
    assert source["status"] == "partial"
    assert "heading\tvalue" in source["sections"][0]["text"]
    assert "read_error" in source["limitation_codes"]


@pytest.mark.parametrize("name", ["bad.pdf", "bad.pptx", "bad.docx", "bad.xlsx", "bad.zip", "bad.csv", "binary.txt"])
def test_malformed_files_are_failed_records_and_batch_continues(tmp_path, name):
    data = b'"unclosed' if name.endswith("csv") else b"\x00broken bytes"
    bad = material(tmp_path, name, data)
    good = material(tmp_path, "good.txt", b"readable")
    manifest = run(tmp_path, [bad, good])
    assert [s["status"] for s in manifest["sources"]] == ["failed", "processed"]
    assert Path(manifest["sources"][0]["storage_path"]).read_bytes() == data


@pytest.mark.parametrize(("extension", "module", "package"), [
    ("pdf", "pypdf", "pypdf"), ("pptx", "pptx", "python-pptx"),
    ("docx", "docx", "python-docx"), ("xlsx", "openpyxl", "openpyxl"),
])
def test_missing_optional_dependency_is_failed_not_success(tmp_path, monkeypatch, extension, module, package):
    data = pdf_bytes() if extension == "pdf" else zipped([("[Content_Types].xml", b"<Types/>")])
    real_import = importlib.import_module

    def missing(name, *args, **kwargs):
        if name == module:
            raise ModuleNotFoundError("synthetic missing dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(ing.importlib, "import_module", missing)
    source = one(tmp_path, material(tmp_path, "자료." + extension, data))
    assert source["status"] == "failed"
    assert source["sections"] == []
    assert "missing_dependency" in source["limitation_codes"]
    assert package in source["limitations"][0]
    assert Path(source["storage_path"]).read_bytes() == data


def test_native_text_does_not_import_optional_libraries(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Native extraction attempted an optional import")

    monkeypatch.setattr(ing.importlib, "import_module", forbidden)
    assert one(tmp_path, material(tmp_path))["status"] == "processed"


def test_real_pdf_text_and_references(tmp_path):
    pytest.importorskip("pypdf")
    source = one(tmp_path, material(tmp_path, "lecture.pdf", pdf_bytes()))
    assert source["status"] == "processed"
    assert source["page_count"] == 1
    assert source["sections"][0]["location"] == "page:1"
    assert "Evidence in a PDF" in source["sections"][0]["text"]


@pytest.mark.parametrize("image", [False, True])
def test_pdf_scan_or_empty_page_requires_multimodal_review(tmp_path, image):
    pytest.importorskip("pypdf")
    source = one(tmp_path, material(tmp_path, "기출.pdf", pdf_bytes(text=b"", image=image)))
    assert source["status"] == "partial"
    assert source["page_count"] == 1
    assert source["multimodal_review_required"] and source["unreadable_history"]
    assert source["sections"] == []


def test_pdf_with_text_and_image_is_partial(tmp_path):
    pytest.importorskip("pypdf")
    source = one(tmp_path, material(tmp_path, "image.pdf", pdf_bytes(image=True)))
    assert source["status"] == "partial"
    assert source["sections"] and source["multimodal_review_required"]


def test_encrypted_pdf_is_failed_with_korean_warning(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(200, 200)
    writer.encrypt("synthetic-password")
    buffer = io.BytesIO()
    writer.write(buffer)
    source = one(tmp_path, material(tmp_path, "encrypted.pdf", buffer.getvalue()))
    assert source["status"] == "failed"
    assert "encrypted" in source["limitation_codes"]


def test_pdf_keeps_successful_pages_when_one_page_breaks(tmp_path, monkeypatch):
    class Page(dict):
        def extract_text(self):
            return "readable first page"

    class BadPage(dict):
        def extract_text(self):
            raise ValueError("bad content stream")

    class Reader:
        is_encrypted = False
        pages = [Page(), BadPage()]

    monkeypatch.setattr(ing, "_dependency", lambda *args: type("Module", (), {"PdfReader": lambda *a: Reader()}))
    source = one(tmp_path, material(tmp_path, "partial.pdf", pdf_bytes()))
    assert source["status"] == "partial"
    assert source["page_count"] == 2
    assert source["sections"] == [{"location": "page:1", "text": "readable first page"}]


def test_real_docx_paragraphs_tables_and_source_order(tmp_path):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("첫 문단")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "정의", "값"
    document.add_paragraph("뒤 문단")
    buffer = io.BytesIO()
    document.save(buffer)
    source = one(tmp_path, material(tmp_path, "문서.docx", buffer.getvalue()))
    assert source["status"] == "processed"
    assert source["sections"] == [
        {"location": "paragraph:1", "text": "첫 문단"},
        {"location": "table:1:rows:1-1", "text": "정의\t값"},
        {"location": "paragraph:2", "text": "뒤 문단"},
    ]


def test_docx_image_requires_review(tmp_path):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("Image caption")
    pixel = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/a9sAAAAASUVORK5CYII=")
    document.add_picture(io.BytesIO(pixel))
    buffer = io.BytesIO()
    document.save(buffer)
    source = one(tmp_path, material(tmp_path, "image.docx", buffer.getvalue()))
    assert source["status"] == "partial"
    assert source["multimodal_review_required"]


def test_real_pptx_slides_tables_groups_and_notes(tmp_path):
    pptx = pytest.importorskip("pptx")
    presentation = pptx.Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_textbox(0, 0, 1000000, 1000000).text = "Slide evidence"
    group = slide.shapes.add_group_shape()
    group.shapes.add_textbox(0, 0, 1000000, 1000000).text = "Grouped evidence"
    table = slide.shapes.add_table(1, 2, 0, 0, 1000000, 1000000).table
    table.cell(0, 0).text, table.cell(0, 1).text = "Definition", "Value"
    slide.notes_slide.notes_text_frame.text = "Speaker evidence"
    buffer = io.BytesIO()
    presentation.save(buffer)
    source = one(tmp_path, material(tmp_path, "lecture_slides.pptx", buffer.getvalue()))
    assert source["status"] == "processed"
    assert source["page_count"] == 1
    assert source["sections"][0]["location"] == "slide:1"
    assert "Grouped evidence" in source["sections"][0]["text"]
    assert "Definition\tValue" in source["sections"][0]["text"]
    assert source["sections"][1] == {"location": "slide:1:notes", "text": "Speaker evidence"}


def test_blank_pptx_requires_review(tmp_path):
    pptx = pytest.importorskip("pptx")
    presentation = pptx.Presentation()
    presentation.slides.add_slide(presentation.slide_layouts[6])
    buffer = io.BytesIO()
    presentation.save(buffer)
    source = one(tmp_path, material(tmp_path, "blank.pptx", buffer.getvalue()))
    assert source["status"] == "partial"
    assert source["multimodal_review_required"]


def workbook_bytes(formula=False):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "자료"
    sheet.append(["이름", "값"])
    sheet.append(["항목", "=1+1" if formula else 7])
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_real_xlsx_read_only_data_only_and_no_links(tmp_path, monkeypatch):
    openpyxl = pytest.importorskip("openpyxl")
    data = workbook_bytes()
    real_load = openpyxl.load_workbook
    calls = []

    def load(*args, **kwargs):
        calls.append(kwargs)
        return real_load(*args, **kwargs)

    monkeypatch.setattr(openpyxl, "load_workbook", load)
    source = one(tmp_path, material(tmp_path, "table.xlsx", data))
    assert source["status"] == "processed"
    assert calls == [{"read_only": True, "data_only": True, "keep_links": False}]
    assert source["sections"] == [{"location": "sheet:1:rows:1-2", "text": "[자료]\n이름\t값\n항목\t7"}]


def test_xlsx_uncached_formulas_are_partial_and_never_evaluated(tmp_path):
    source = one(tmp_path, material(tmp_path, "formula.xlsx", workbook_bytes(formula=True)))
    assert source["status"] == "partial"
    assert source["formula_count"] == source["uncached_formula_count"] == 1
    assert "uncached_formulas" in source["limitation_codes"]
    assert "=1+1" not in str(source["sections"])


def test_xlsx_reads_cached_formula_value(tmp_path):
    data = workbook_bytes(formula=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = [(i.filename, archive.read(i).replace(b"<f>1+1</f><v></v>", b"<f>1+1</f><v>2</v>")) for i in archive.infolist()]
    source = one(tmp_path, material(tmp_path, "cached.xlsx", zipped(entries)))
    assert source["status"] == "processed"
    assert source["formula_count"] == 1 and source["uncached_formula_count"] == 0
    assert "항목\t2" in source["sections"][0]["text"]


@pytest.mark.parametrize("extension", ["png", "jpg", "jpeg", "webp", "tiff", "heic"])
def test_image_requires_review_without_fake_ocr(tmp_path, extension):
    source = one(tmp_path, material(tmp_path, "scan." + extension, b"synthetic image placeholder"))
    assert source["status"] == "partial"
    assert source["multimodal_review_required"] and not source["sections"]


@pytest.mark.parametrize("extension", ["doc", "ppt", "xls", "exe", "docm", "pptm", "xlsm"])
def test_legacy_and_unsupported_content_is_not_executed(tmp_path, extension):
    source = one(tmp_path, material(tmp_path, "material." + extension, b"synthetic embedded content"))
    assert source["status"] == "failed"
    assert source["limitation_codes"] == ["legacy_format" if extension in {"doc", "ppt", "xls"} else "unsupported_format"]
    assert Path(source["storage_path"]).read_bytes() == b"synthetic embedded content"


def test_archive_members_have_distinct_stable_ids_and_qualified_names(tmp_path):
    data = b"identical source text"
    original = material(tmp_path, "notes.txt", data)
    archive = material(tmp_path, "bundle.zip", zipped([("a/notes.txt", data), ("b/notes.txt", data)]))
    manifest = run(tmp_path, [original, archive])
    assert len(manifest["sources"]) == 4
    ids = [s["id"] for s in manifest["sources"]]
    assert len(set(ids)) == 4
    assert manifest["sources"][2]["id"].startswith("member_")
    assert manifest["sources"][2]["sha256"] == manifest["sources"][0]["sha256"]
    assert manifest["sources"][2]["filename"] == "bundle.zip!/a/notes.txt"
    assert manifest["sources"][2]["archive_parent_id"] == manifest["sources"][1]["id"]
    assert Path(manifest["sources"][2]["storage_path"]).name == hashlib.sha256(data).hexdigest()
    assert [s["id"] for s in run(tmp_path, [original, archive])["sources"]] == ids
    assert manifest["counts"]["archive_members"] == 2
    assert all(s["status"] == "processed" for s in manifest["sources"])


def test_archive_member_override_by_qualified_name_wins_over_basename(tmp_path):
    archive = material(tmp_path, "bundle.zip", zipped([("a/source.txt", b"text")]))
    manifest = run(tmp_path, [archive], {"source.txt": "other", "bundle.zip!/a/source.txt": "syllabus"})
    assert manifest["sources"][1]["category"] == "syllabus"


def test_archive_solution_only_member_does_not_prove_history(tmp_path):
    archive = material(tmp_path, "bundle.zip", zipped([("past_exam_solutions.pdf", b"bad PDF")]))
    manifest = run(tmp_path, [archive])
    assert manifest["sources"][1]["category"] == "official_solution"
    assert not any(s["suspected_history"] for s in manifest["sources"])


def test_archive_member_failures_propagate_to_container(tmp_path):
    archive = material(tmp_path, "bundle.zip", zipped([("good.txt", b"good"), ("bad.pdf", b"bad")]))
    manifest = run(tmp_path, [archive])
    assert [s["status"] for s in manifest["sources"]] == ["partial", "processed", "failed"]


@pytest.mark.parametrize("name", [
    "../escape.txt", "a/../../escape.txt", "/absolute.txt", "C:/drive.txt", "C:relative.txt",
    "\\\\host\\share\\file.txt", "a\\..\\escape.txt", "a/./file.txt", "a//file.txt",
    "a/file.txt:stream", "CON.txt", "AUX", "a/trailing. ", "a\x01bad.txt",
])
def test_archive_unsafe_paths_rejected_before_any_member_is_copied(tmp_path, name):
    archive = material(tmp_path, "unsafe.zip", zipped([("safe.txt", b"good"), (name, b"bad")]))
    manifest = run(tmp_path, [archive])
    assert len(manifest["sources"]) == 1
    assert manifest["sources"][0]["status"] == "failed"
    assert "unsafe_archive_path" in manifest["sources"][0]["limitation_codes"]
    assert len(list((tmp_path / "private" / "originals").iterdir())) == 1
    assert not (tmp_path / "escape.txt").exists()


def test_nul_archive_name_is_rejected():
    info = zipfile.ZipInfo("safe.txt\x00../hidden.txt")
    with pytest.raises(ing._IngestionError, match="안전하지 않은"):
        ing._member_name(info)


@pytest.mark.parametrize("mode", [stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600, stat.S_IFCHR | 0o600])
def test_archive_symlinks_and_special_files_rejected(tmp_path, mode):
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = mode << 16
    source = one(tmp_path, material(tmp_path, "links.zip", zipped([(info, b"../target")])))
    assert source["status"] == "failed"
    assert "archive_link" in source["limitation_codes"]


def test_archive_windows_reparse_attribute_rejected(tmp_path):
    info = zipfile.ZipInfo("junction")
    info.create_system = 0
    info.external_attr = 0x400
    source = one(tmp_path, material(tmp_path, "links.zip", zipped([(info, b"target")])))
    assert source["status"] == "failed"
    assert "archive_link" in source["limitation_codes"]


@pytest.mark.parametrize("second", ["same.txt", "SAME.txt", "a\\b.txt"])
def test_archive_duplicate_paths_rejected(tmp_path, second):
    first = "a/b.txt" if "b.txt" in second else "same.txt"
    archive = material(tmp_path, "duplicates.zip", zipped([(first, b"a"), (second, b"b")]))
    source = one(tmp_path, archive)
    assert source["status"] == "failed"
    assert "archive_duplicate_path" in source["limitation_codes"]


def test_zip_bomb_ratio_rejected(tmp_path):
    archive = material(tmp_path, "bomb.zip", zipped([("huge.txt", b"x" * 200_000)], zipfile.ZIP_DEFLATED))
    source = one(tmp_path, archive)
    assert source["status"] == "failed"
    assert "archive_ratio_limit" in source["limitation_codes"]


def test_zip_total_uncompressed_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(ing, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 10)
    source = one(tmp_path, material(tmp_path, "large.zip", zipped([("a.txt", b"123456"), ("b.txt", b"123456")])))
    assert source["status"] == "failed"
    assert "archive_size_limit" in source["limitation_codes"]


def test_zip_member_count_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(ing, "MAX_ARCHIVE_MEMBERS", 1)
    source = one(tmp_path, material(tmp_path, "many.zip", zipped([("a.txt", b"a"), ("b.txt", b"b")])))
    assert source["status"] == "failed"
    assert "archive_file_limit" in source["limitation_codes"]


def test_rejected_zip_with_historical_member_fails_closed(tmp_path):
    source = one(tmp_path, material(tmp_path, "bundle.zip", zipped([("../기출.pdf", b"bad")])))
    assert source["status"] == "failed"
    assert source["category"] == "historical_exam"
    assert source["suspected_history"] and source["unreadable_history"]


def test_nested_archive_depth_is_bounded_and_all_references_remain_unique(tmp_path, monkeypatch):
    monkeypatch.setattr(ing, "MAX_ARCHIVE_DEPTH", 2)
    inner = zipped([("notes.txt", b"deep content")])
    middle = zipped([("inner.zip", inner)])
    outer = zipped([("middle.zip", middle)])
    manifest = run(tmp_path, [material(tmp_path, "outer.zip", outer)])
    assert len(manifest["sources"]) == 3
    assert len({s["id"] for s in manifest["sources"]}) == 3
    assert all(s["status"] == "failed" for s in manifest["sources"])
    assert "archive_depth_limit" in manifest["sources"][-1]["limitation_codes"]
    assert manifest["sources"][-1]["filename"] == "outer.zip!/middle.zip!/inner.zip"


def test_total_file_limit_bounds_generator_consumption(tmp_path, monkeypatch):
    monkeypatch.setattr(ing, "MAX_FILES", 2)
    path = material(tmp_path)
    consumed = []

    def inputs():
        for number in range(100_000):
            consumed.append(number)
            yield path

    manifest = run(tmp_path, inputs())
    assert len(consumed) == 3
    assert manifest["counts"]["failed"] == 1
    assert "file_limit" in manifest["sources"][-1]["limitation_codes"]


def test_file_count_includes_archive_members(tmp_path, monkeypatch):
    monkeypatch.setattr(ing, "MAX_FILES", 2)
    source = one(tmp_path, material(tmp_path, "many.zip", zipped([("a.txt", b"a"), ("b.txt", b"b")])))
    assert source["status"] == "failed"
    assert "file_limit" in source["limitation_codes"]


def test_per_file_and_total_byte_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(ing, "MAX_INPUT_BYTES", 10)
    large = material(tmp_path, "기출.txt", b"x" * 11)
    source = one(tmp_path, large)
    assert source["status"] == "failed" and source["sha256"] is None
    assert source["storage_path"] is None and source["unreadable_history"]
    monkeypatch.setattr(ing, "MAX_TOTAL_INPUT_BYTES", 5)
    manifest = run(tmp_path, [material(tmp_path, "a.txt", b"12345"), material(tmp_path, "b.txt", b"b")])
    assert [s["status"] for s in manifest["sources"]] == ["processed", "failed"]
    assert "total_size_limit" in manifest["sources"][1]["limitation_codes"]


def test_actual_stream_read_is_bounded_without_trusting_metadata():
    stream = io.BytesIO(b"x" * 100)
    with pytest.raises(ing._IngestionError):
        ing._read_limited(stream, 5)
    assert stream.tell() == 6


def test_empty_files_are_partial_and_empty_zip_failed(tmp_path):
    source = one(tmp_path, material(tmp_path, "empty.txt", b""))
    assert source["status"] == "partial" and "empty_content" in source["limitation_codes"]
    source = one(tmp_path, material(tmp_path, "empty.zip", zipped([])))
    assert source["status"] == "failed" and "empty_archive" in source["limitation_codes"]


def test_missing_path_and_directory_are_failed_with_nullable_digest(tmp_path):
    directory = tmp_path / "folder"
    directory.mkdir()
    manifest = run(tmp_path, [tmp_path / "기출.pdf", directory])
    assert len(manifest["sources"]) == 2
    for source in manifest["sources"]:
        assert source["status"] == "failed" and source["sha256"] is None
        assert source["id"].startswith("rejected_")
        assert source["storage_path"] is None
    assert manifest["sources"][0]["unreadable_history"]


def test_storage_conflict_is_preserved_and_reported(tmp_path):
    data = b"original bytes"
    path = material(tmp_path, data=data)
    target = tmp_path / "private" / "originals" / hashlib.sha256(data).hexdigest()
    target.parent.mkdir(parents=True)
    replacement = b"X" * len(data)
    target.write_bytes(replacement)
    source = one(tmp_path, path)
    assert source["status"] == "failed"
    assert source["limitation_codes"] == ["storage_conflict"]
    assert target.read_bytes() == replacement
    assert path.read_bytes() == data


def symlink_or_skip(link, target, is_dir=False):
    try:
        os.symlink(target, link, target_is_directory=is_dir)
    except (OSError, NotImplementedError):
        pytest.skip("Host does not grant symlink creation rights")


def test_source_symlink_is_rejected(tmp_path):
    path = material(tmp_path)
    link = tmp_path / "linked.txt"
    symlink_or_skip(link, path)
    source = one(tmp_path, link)
    assert source["status"] == "failed" and source["sha256"] is None
    assert "unsafe_path" in source["limitation_codes"]


def test_storage_symlink_is_rejected_without_writing_to_target(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "private"
    symlink_or_skip(link, target, True)
    with pytest.raises(ValueError, match="심볼릭 링크"):
        one(tmp_path, material(tmp_path))
    assert not list(target.iterdir())


def test_existing_stored_symlink_is_not_followed(tmp_path):
    data = b"original"
    path = material(tmp_path, data=data)
    target = material(tmp_path, "victim.txt", b"untouched")
    store = tmp_path / "private" / "originals"
    store.mkdir(parents=True)
    symlink_or_skip(store / hashlib.sha256(data).hexdigest(), target)
    source = one(tmp_path, path)
    assert source["status"] == "failed"
    assert "storage_conflict" in source["limitation_codes"]
    assert target.read_bytes() == b"untouched"


def test_storage_under_own_checkout_is_rejected():
    checkout = Path(ing.__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="소스 폴더 밖"):
        ing.ingest([], checkout / "forbidden-private")
    assert not (checkout / "forbidden-private").exists()


@pytest.mark.parametrize("extension", ["docx", "pptx", "xlsx"])
def test_ooxml_zip_security_checks_precede_optional_reader(tmp_path, monkeypatch, extension):
    def forbidden(*args, **kwargs):
        pytest.fail("Unsafe archive reached a document parser")

    monkeypatch.setattr(ing, "_dependency", forbidden)
    source = one(tmp_path, material(tmp_path, "bad." + extension, zipped([("../payload.xml", b"<a/>")])))
    assert source["status"] == "failed"
    assert "unsafe_archive_path" in source["limitation_codes"]


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_ooxml_entity_declarations_are_rejected(tmp_path, encoding):
    xml = '<!DOCTYPE x [<!ENTITY payload SYSTEM "file:///private">]><x>&payload;</x>'.encode(encoding)
    source = one(tmp_path, material(tmp_path, "unsafe.docx", zipped([("word/document.xml", xml)])))
    assert source["status"] == "failed"
    assert "unsafe_xml" in source["limitation_codes"]


def test_corrupted_zip_member_crc_is_reported(tmp_path):
    data = bytearray(zipped([("note.txt", b"unique original payload")]))
    offset = data.index(b"unique original payload")
    data[offset] ^= 1
    manifest = run(tmp_path, [material(tmp_path, "corrupt.zip", bytes(data))])
    assert [s["status"] for s in manifest["sources"]] == ["failed", "failed"]
    assert "archive_member_error" in manifest["sources"][1]["limitation_codes"]


def test_encrypted_zip_member_is_explicit_failure(tmp_path):
    data = bytearray(zipped([("secret.txt", b"not really encrypted")]))
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        start = data.index(signature)
        flags = struct.unpack_from("<H", data, start + flag_offset)[0]
        struct.pack_into("<H", data, start + flag_offset, flags | 1)
    manifest = run(tmp_path, [material(tmp_path, "encrypted.zip", bytes(data))])
    assert [s["status"] for s in manifest["sources"]] == ["failed", "failed"]
    assert "encrypted" in manifest["sources"][1]["limitation_codes"]


def test_extracted_character_and_section_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(ing, "MAX_TEXT_CHARS", 5)
    source = one(tmp_path, material(tmp_path, data=b"abcdefg"))
    assert source["status"] == "partial" and source["character_count"] <= 5
    monkeypatch.setattr(ing, "MAX_TEXT_CHARS", 100_000)
    monkeypatch.setattr(ing, "MAX_SECTIONS", 1)
    source = one(tmp_path, material(tmp_path, "manylines.txt", b"line\n" * 90))
    assert source["status"] == "partial" and source["section_count"] == 1


def test_xlsx_cell_limit_is_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(ing, "MAX_SPREADSHEET_CELLS", 2)
    source = one(tmp_path, material(tmp_path, "table.xlsx", workbook_bytes()))
    assert source["status"] == "partial"
    assert "cell_limit" in source["limitation_codes"]


def test_empty_xlsx_does_not_invent_content_from_sheet_title(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    source = one(tmp_path, material(tmp_path, "empty.xlsx", buffer.getvalue()))
    assert source["status"] == "partial"
    assert source["sections"] == []
    assert "empty_content" in source["limitation_codes"]


def test_docx_limited_table_keeps_accurate_row_reference(tmp_path, monkeypatch):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    table = document.add_table(rows=2, cols=1)
    table.cell(0, 0).text = "first row"
    table.cell(1, 0).text = "second row"
    buffer = io.BytesIO()
    document.save(buffer)
    monkeypatch.setattr(ing, "MAX_SPREADSHEET_ROWS", 1)
    source = one(tmp_path, material(tmp_path, "limited.docx", buffer.getvalue()))
    assert source["status"] == "partial"
    assert source["sections"] == [{"location": "table:1:rows:1-1", "text": "first row"}]


def test_ingestion_does_not_open_network_connections_or_execute_archived_scripts(tmp_path, monkeypatch):
    import socket

    marker = tmp_path / "executed.txt"
    script = ("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')").encode()
    archive = material(tmp_path, "bundle.zip", zipped([("notes.txt", b"local evidence"), ("script.py", script)]))

    def forbidden(*args, **kwargs):
        pytest.fail("Ingestion attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    manifest = run(tmp_path, [archive])
    assert not marker.exists()
    assert [s["status"] for s in manifest["sources"]] == ["partial", "processed", "failed"]
    assert "unsupported_format" in manifest["sources"][-1]["limitation_codes"]


def test_student_warnings_are_korean_and_limitation_counts_match(tmp_path):
    paths = [material(tmp_path, "legacy.doc", b"legacy"), material(tmp_path, "image.png", b"image"), tmp_path / "missing.pdf"]
    manifest = run(tmp_path, paths)
    for source in manifest["sources"]:
        assert source["limitation_count"] == len(source["limitations"]) == len(source["limitation_codes"])
        assert all(re.search("[가-힣]", message) for message in source["limitations"])
    assert manifest["counts"]["limitations"] == sum(s["limitation_count"] for s in manifest["sources"])
    assert manifest["counts"]["total_sources"] == sum(manifest["counts"][s] for s in ("processed", "partial", "failed"))


def test_invalid_override_is_a_korean_configuration_error(tmp_path):
    with pytest.raises(ValueError, match="분류"):
        run(tmp_path, [], {"notes.txt": "made_up_category"})


def test_empty_batch_is_valid(tmp_path):
    manifest = run(tmp_path, [])
    assert manifest["schema_version"] == 1 and manifest["sources"] == []
    assert manifest["counts"]["total_sources"] == 0
