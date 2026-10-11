# Complete A-to-Z PDF Metadata Remover

A high-performance Python tool to completely sanitize and purge all metadata from any number of PDF files (**1, 5, 50, 500+ files**), saving each file to the output destination with its **exact original filename**.

---

## What Gets Removed ("A to Z" Cleaning)

1. **Standard Document Information (`/Info`)**:
   - `Title`, `Author`, `Subject`, `Keywords`, `Creator`, `Producer`
   - `CreationDate`, `ModDate`, `Trapped`
   - All custom software keys (`Company`, `SourceModified`, etc.)
2. **Catalog Extensible Metadata Platform (XMP/XML)**:
   - Full Adobe XMP metadata packet (`/Metadata`)
   - Dublin Core (`dc:`), Photoshop (`photoshop:`), XMP Basic schemas
3. **Internal & Embedded Object Metadata**:
   - Object-level `/Metadata` streams on pages, fonts, and images
   - `/PieceInfo` dictionaries (private Adobe Illustrator, Photoshop, and InDesign metadata)
   - Embedded preview thumbnails (`/Thumb`)
4. **Annotation Tracking**:
   - User names and author attribution in annotations/notes
   - Annotation creation and modification timestamps
5. **Incremental Revision History & Dead Objects**:
   - Full cross-reference table rebuild with garbage collection (`garbage=4`), purging historical revisions where old deleted metadata lingers in raw bytes.

---

## Requirements

```bash
pip install -r requirements.txt
```
*(or `pip install pymupdf`)*

---

## How to Use with Multiple Files

### 1. Drop-in Folder Batch Mode (Handles any number of files)
Put as many PDF files as you want (5, 50, 100+) into the `input/` folder, then run:

```bash
python pdf_metadata_remover.py
```
All files will be cleaned in parallel and saved to `output/` with their original names.

---

### 2. Pass Multiple Files Directly in Command Line
You can list 6 or more files directly:

```bash
python pdf_metadata_remover.py -i file1.pdf file2.pdf file3.pdf file4.pdf file5.pdf file6.pdf -o output/
```

Or use wildcard globbing to match all PDFs in a folder:

```bash
python pdf_metadata_remover.py -i /path/to/my_pdfs/*.pdf -o output/
```

---

### 3. Subfolder Recursive Mode
If you have PDFs inside nested subdirectories:

```bash
python pdf_metadata_remover.py -i input/ -o output/ --recursive
```

---

### 4. Custom Speed / Multi-Threading
For large batches (e.g., 50+ files), specify more parallel worker threads:

```bash
python pdf_metadata_remover.py -i input/ -o output/ --workers 8
```
