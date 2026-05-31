import fitz  # PyMuPDF
from pathlib import Path
import shutil

source_dir = Path("/home/alucard/Downloads/AI Bot/clones")
dest_dir = Path("/home/alucard/Downloads/AI Bot/backend/clones/alucard/data")

# Ensure dest dir exists
dest_dir.mkdir(parents=True, exist_ok=True)

# 1. Process PDFs
pdfs = [
    "2015.499492.the-diaries.pdf",
    "frans_kafka_milenaya_mektublar-eng.pdf",
    "letter-to-my-father.pdf"
]

for pdf_name in pdfs:
    pdf_path = source_dir / pdf_name
    if not pdf_path.exists():
        print(f"Missing PDF: {pdf_name}")
        continue
    
    print(f"Extracting: {pdf_name}")
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n\n"
    
    txt_name = pdf_name.replace(".pdf", ".txt")
    with open(dest_dir / txt_name, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Saved: {txt_name} ({len(text)} chars)")

# 2. Copy TXT files
txts = [
    "The_Metamorphosis.txt",
    "The_trail.txt",
    "complete_short_stories.txt"
]

for txt_name in txts:
    src_path = source_dir / txt_name
    if not src_path.exists():
        print(f"Missing TXT: {txt_name}")
        continue
        
    shutil.copy2(src_path, dest_dir / txt_name)
    print(f"Copied: {txt_name}")

print("Extraction complete.")
