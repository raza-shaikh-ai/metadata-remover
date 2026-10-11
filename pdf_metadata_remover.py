#!/usr/bin/env python3
"""
Complete A-to-Z PDF Metadata Remover (Multi-File & Batch Supported)
===================================================================
Exhaustively purges all metadata, XMP streams, private application data,
thumbnails, tracking IDs, and revision history from any number of PDF files.
All cleaned files are saved to the output destination with their original names.

Key Features:
- Handles 1, 5, 50, or 500+ files seamlessly.
- Accepts multiple files, wildcards (*.pdf), or directories.
- Optional multi-threaded parallel processing for fast batch operations.
- Recursive directory scanning option (-r / --recursive).
- Preserves identical filenames in the output.
"""

import os
import sys
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import fitz  # PyMuPDF
except ImportError:
    print("[ERROR] PyMuPDF is not installed. Please run: pip install pymupdf")
    sys.exit(1)


def get_metadata_summary(doc: fitz.Document) -> dict:
    """Extract a summary of all metadata currently in the PDF document."""
    meta = doc.metadata or {}
    non_empty_meta = {k: v for k, v in meta.items() if v and k != "format"}
    xml_len = len(doc.get_xml_metadata() or "")

    piece_info_count = 0
    metadata_streams_count = 0

    for xref in range(1, doc.xref_length()):
        try:
            if doc.xref_get_key(xref, "Type")[1] == "/Metadata":
                metadata_streams_count += 1
            if doc.xref_get_key(xref, "PieceInfo")[0] != "null":
                piece_info_count += 1
        except Exception:
            pass

    return {
        "standard_fields": non_empty_meta,
        "xmp_bytes": xml_len,
        "extra_objects": metadata_streams_count + piece_info_count,
    }


def clean_single_pdf(input_path: Path, output_path: Path, verbose: bool = False) -> tuple[bool, str]:
    """
    Exhaustively purges all metadata from a single PDF and writes to output_path.
    Returns (success: bool, status_message: str).
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        return False, f"File not found: {input_path}"

    if input_path.resolve() == output_path.resolve():
        return False, f"Skipped (input and output path cannot be identical: {input_path})"

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Could not create output directory: {e}"

    try:
        doc = fitz.open(input_path)
    except Exception as e:
        return False, f"Could not open file: {e}"

    if doc.is_encrypted:
        if not doc.authenticate(""):
            doc.close()
            return False, "File is encrypted/password-protected"

    before_summary = get_metadata_summary(doc)

    # 1. Clear standard document info dictionary
    doc.set_metadata({})

    # 2. Delete catalog XMP XML stream
    try:
        doc.del_xml_metadata()
    except Exception:
        pass

    # 3. Scan and strip all xref objects for hidden metadata
    for xref in range(1, doc.xref_length()):
        try:
            # Clear /Type /Metadata objects
            if doc.xref_get_key(xref, "Type")[1] == "/Metadata":
                doc.update_object(xref, "<<>>")
                doc.update_stream(xref, b"")

            # Remove /Metadata pointer on pages/fonts/images
            if doc.xref_get_key(xref, "Metadata")[0] != "null":
                doc.xref_set_key(xref, "Metadata", "null")

            # Remove /PieceInfo (Adobe Illustrator/Photoshop/InDesign private data)
            if doc.xref_get_key(xref, "PieceInfo")[0] != "null":
                doc.xref_set_key(xref, "PieceInfo", "null")

            # Remove /Thumb (page thumbnail previews)
            if doc.xref_get_key(xref, "Thumb")[0] != "null":
                doc.xref_set_key(xref, "Thumb", "null")
        except Exception:
            pass

    # 4. Sanitize page-level metadata & annotation author info
    for page in doc:
        try:
            doc.xref_set_key(page.xref, "PieceInfo", "null")
        except Exception:
            pass
        try:
            doc.xref_set_key(page.xref, "Metadata", "null")
        except Exception:
            pass

        for annot in page.annots():
            try:
                info = annot.info
                info["title"] = ""        # Author/user name
                info["modDate"] = ""      # Modification timestamp
                info["creationDate"] = "" # Creation timestamp
                annot.set_info(info)
            except Exception:
                pass

    # 5. Save with maximum garbage collection & stream sanitation
    try:
        doc.save(
            str(output_path),
            garbage=4,
            clean=True,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            preserve_metadata=0,
        )
    except Exception as e:
        doc.close()
        return False, f"Failed to save: {e}"

    doc.close()

    fields_count = len(before_summary["standard_fields"])
    xmp_size = before_summary["xmp_bytes"]
    details = f"Purged {fields_count} field(s), {xmp_size} XMP bytes"
    return True, details


def collect_pdf_files(inputs: list[str], recursive: bool = False) -> list[Path]:
    """Collects and deduplicates all PDF files from given file/directory inputs."""
    pdf_files = []
    seen = set()

    for item in inputs:
        p = Path(item)
        if p.is_file() and p.suffix.lower() == ".pdf":
            resolved = p.resolve()
            if resolved not in seen:
                seen.add(resolved)
                pdf_files.append(p)
        elif p.is_dir():
            pattern = "**/*.pdf" if recursive else "*.pdf"
            for found in sorted(p.glob(pattern)):
                resolved = found.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    pdf_files.append(found)
        else:
            # Handle shell glob patterns if not expanded by the shell
            parent = p.parent if str(p.parent) != "." else Path(".")
            name_pattern = p.name
            if any(char in name_pattern for char in ["*", "?", "["]):
                for matched in sorted(parent.glob(name_pattern)):
                    if matched.suffix.lower() == ".pdf":
                        resolved = matched.resolve()
                        if resolved not in seen:
                            seen.add(resolved)
                            pdf_files.append(matched)

    return sorted(pdf_files, key=lambda f: f.name.lower())


def process_files(
    inputs: list[str],
    output_target: str,
    recursive: bool = False,
    workers: int = 4
) -> None:
    """Processes any number of input PDFs and saves to output directory with same names."""
    out_dir = Path(output_target)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = collect_pdf_files(inputs, recursive=recursive)

    if not pdf_files:
        print("[INFO] No PDF files found matching your input.")
        print("       Drop PDFs into the 'input/' folder or specify file paths.")
        return

    total = len(pdf_files)
    print(f"\n==================================================")
    print(f" PDF Metadata Remover - Processing {total} file(s)")
    print(f" Output folder: {out_dir.resolve()}")
    print(f" Mode: {'Parallel (' + str(workers) + ' threads)' if workers > 1 and total > 1 else 'Sequential'}")
    print(f"==================================================\n")

    tasks = []
    for pdf in pdf_files:
        target_path = out_dir / pdf.name  # Preserves exact same file name
        tasks.append((pdf, target_path))

    successes = 0
    failures = 0

    if workers > 1 and total > 1:
        # Multi-threaded batch processing for fast handling of many files
        with ThreadPoolExecutor(max_workers=min(workers, total)) as executor:
            future_to_task = {
                executor.submit(clean_single_pdf, src, dst): (idx + 1, src, dst)
                for idx, (src, dst) in enumerate(tasks)
            }
            for future in as_completed(future_to_task):
                idx, src, dst = future_to_task[future]
                try:
                    ok, msg = future.result()
                    if ok:
                        successes += 1
                        print(f"  [{idx:3d}/{total:3d}] ✓ {src.name} -> {msg}")
                    else:
                        failures += 1
                        print(f"  [{idx:3d}/{total:3d}] ✗ {src.name} -> ERROR: {msg}")
                except Exception as exc:
                    failures += 1
                    print(f"  [{idx:3d}/{total:3d}] ✗ {src.name} -> EXCEPTION: {exc}")
    else:
        # Sequential processing
        for idx, (src, dst) in enumerate(tasks, 1):
            ok, msg = clean_single_pdf(src, dst)
            if ok:
                successes += 1
                print(f"  [{idx:3d}/{total:3d}] ✓ {src.name} -> {msg}")
            else:
                failures += 1
                print(f"  [{idx:3d}/{total:3d}] ✗ {src.name} -> ERROR: {msg}")

    print(f"\n==================================================")
    print(f" COMPLETED: {successes}/{total} files successfully cleaned")
    if failures > 0:
        print(f" WARNING:   {failures} file(s) failed (check logs above)")
    print(f" Saved in:  {out_dir.resolve()}")
    print(f"==================================================\n")


def main():
    parser = argparse.ArgumentParser(
        description="Complete A-to-Z PDF Metadata Remover: easily cleans 1, 5, 50, or hundreds of PDFs."
    )
    parser.add_argument(
        "-i", "--input",
        nargs="+",
        default=["input"],
        help="Input PDF file(s), wildcard (e.g. *.pdf), or input folder (default: input/)"
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="Destination folder where cleaned PDFs are saved with the same names (default: output/)"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively scan subfolders for PDF files"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=4,
        help="Number of parallel worker threads (default: 4)"
    )

    args = parser.parse_args()

    # Automatically set up default folders if using defaults and input is empty
    if args.input == ["input"] and not Path("input").exists():
        Path("input").mkdir(parents=True, exist_ok=True)
        Path("output").mkdir(parents=True, exist_ok=True)
        print("[SETUP] Created './input' and './output' folders.")
        print("Drop your PDF files (any number) into 'input/' and run:")
        print("  python pdf_metadata_remover.py\n")
        return

    process_files(
        inputs=args.input,
        output_target=args.output,
        recursive=args.recursive,
        workers=args.workers
    )


if __name__ == "__main__":
    main()
