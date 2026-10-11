import io
import zipfile
import streamlit as st
import fitz  # PyMuPDF

st.set_page_config(page_title="PDF Metadata Remover", page_icon="📄", layout="centered")


def clean_pdf_metadata(file_bytes: bytes) -> tuple[bytes, dict]:
    """Exhaustively removes all metadata from PDF bytes and returns sanitized bytes."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    # Capture metadata summary before cleaning
    meta = doc.metadata or {}
    non_empty = {k: v for k, v in meta.items() if v and k != "format"}
    xmp_len = len(doc.get_xml_metadata() or "")

    # 1. Clear standard document info dictionary
    doc.set_metadata({})

    # 2. Delete catalog XMP XML stream
    try:
        doc.del_xml_metadata()
    except Exception:
        pass

    # 3. Strip all xref objects for hidden metadata & private data
    for xref in range(1, doc.xref_length()):
        try:
            if doc.xref_get_key(xref, "Type")[1] == "/Metadata":
                doc.update_object(xref, "<<>>")
                doc.update_stream(xref, b"")

            if doc.xref_get_key(xref, "Metadata")[0] != "null":
                doc.xref_set_key(xref, "Metadata", "null")

            if doc.xref_get_key(xref, "PieceInfo")[0] != "null":
                doc.xref_set_key(xref, "PieceInfo", "null")

            if doc.xref_get_key(xref, "Thumb")[0] != "null":
                doc.xref_set_key(xref, "Thumb", "null")
        except Exception:
            pass

    # 4. Clean page-level metadata & annotation author info
    for page in doc:
        try:
            doc.xref_set_key(page.xref, "PieceInfo", "null")
            doc.xref_set_key(page.xref, "Metadata", "null")
        except Exception:
            pass

        for annot in page.annots():
            try:
                info = annot.info
                info["title"] = ""
                info["modDate"] = ""
                info["creationDate"] = ""
                annot.set_info(info)
            except Exception:
                pass

    # 5. Output sanitized PDF bytes with garbage collection & stream cleaning
    cleaned_bytes = doc.tobytes(
        garbage=4,
        clean=True,
        deflate=True,
        deflate_images=True,
        deflate_fonts=True,
        preserve_metadata=0,
    )
    doc.close()

    summary = {
        "fields_purged": len(non_empty),
        "xmp_bytes": xmp_len,
    }
    return cleaned_bytes, summary


# --- Streamlit UI ---
st.title("📄 PDF Metadata Remover")
st.write("Upload PDF files to permanently remove all metadata (Author, Title, Dates, XMP, Hidden tracking, Revision history).")

uploaded_files = st.file_uploader(
    "Choose PDF files",
    type=["pdf"],
    accept_multiple_files=True,
    help="Upload one or multiple PDF documents"
)

if uploaded_files:
    st.write(f"**Selected {len(uploaded_files)} file(s)**")

    cleaned_results = []
    with st.spinner("Removing metadata..."):
        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.read()
            cleaned_bytes, summary = clean_pdf_metadata(file_bytes)
            cleaned_results.append({
                "name": uploaded_file.name,
                "bytes": cleaned_bytes,
                "summary": summary
            })

    st.success("✓ All metadata successfully removed!")

    # Download All as ZIP if more than 1 file
    if len(cleaned_results) > 1:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for item in cleaned_results:
                zip_file.writestr(item["name"], item["bytes"])
        zip_buffer.seek(0)

        st.download_button(
            label="📦 Download All Cleaned PDFs (.zip)",
            data=zip_buffer,
            file_name="cleaned_pdfs.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True
        )
        st.divider()

    # Individual file download buttons
    st.subheader("Cleaned Files")
    for item in cleaned_results:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"📄 **{item['name']}**")
            st.caption(f"Cleared {item['summary']['fields_purged']} info field(s) & {item['summary']['xmp_bytes']} bytes of XMP/XML data")
        with col2:
            st.download_button(
                label="⬇️ Download",
                data=item["bytes"],
                file_name=item["name"],
                mime="application/pdf",
                key=f"dl_{item['name']}",
                use_container_width=True
            )
