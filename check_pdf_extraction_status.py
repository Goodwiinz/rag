#!/usr/bin/env python3
import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from pathlib import Path

# Check the PDF files that should have been processed
ARXIV_DATA_PATH = Path("/Users/goodwiinz/development/RAG_system/data/processed_pdfs/arxiv")

print("=== Local PDF Files Check ===\n")

# List all PDF files
pdf_files = list(ARXIV_DATA_PATH.glob("*.pdf"))
pdf_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

print(f"Found {len(pdf_files)} PDF files:\n")

for i, pdf_file in enumerate(pdf_files[:10], 1):
    file_size = pdf_file.stat().st_size / (1024 * 1024)  # MB
    modified = pdf_file.stat().st_mtime

    import datetime
    modified_date = datetime.datetime.fromtimestamp(modified).strftime("%Y-%m-%d %H:%M:%S")

    print(f"{i}. {pdf_file.stem}")
    print(f"   📁 Full path: {pdf_file}")
    print(f"   📊 Size: {file_size:.2f} MB")
    print(f"   📅 Modified: {modified_date}")
    print()

# Check if the PDFs have corresponding extraction files
print("\n" + "=" * 60)
print("📋 Extraction Status:")
print("=" * 60)

for pdf_file in pdf_files[:7]:  # Check the first 7
    paper_id = pdf_file.stem

    # Check for various possible extraction files
    txt_file = pdf_file.with_suffix('.txt')
    json_file = pdf_file.with_suffix('.json')

    print(f"\n📄 {paper_id}")
    print(f"   PDF exists: {pdf_file.exists()}")
    print(f"   TXT exists: {txt_file.exists()}")
    print(f"   JSON exists: {json_file.exists()}")

    # Check text content if exists
    if txt_file.exists():
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"   Text length: {len(content)} characters")
                print(f"   Text preview: {content[:200]}...")
        except Exception as e:
            print(f"   Error reading TXT: {e}")