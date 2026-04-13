"""
batch_upload.py - Process up to 500 resumes concurrently
Usage: python batch_upload.py --folder ./resumes --workers 3 --delay 1.0
"""

import os
import time
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

API_URL = "http://localhost:5000/uploadresume"


def upload_resume(filepath):
    filename = os.path.basename(filepath)
    try:
        with open(filepath, 'rb') as f:
            response = requests.post(
                API_URL,
                files={'resume': (filename, f, 'application/pdf')},
                timeout=60   # generous timeout for PDF extract + details
            )
        if response.status_code == 200:
            data = response.json()
            return {
                "file":      filename,
                "status":    "Success",
                "candidate": data.get("candidate", "Unknown"),
                "jobs":      data.get("jobs_found", "processing..."),
                "link":      data.get("interview_link", ""),
                "note":      data.get("note", "")
            }
        else:
            return {
                "file":   filename,
                "status": "HTTP Error " + str(response.status_code),
                "error":  response.text[:200]
            }
    except requests.exceptions.Timeout:
        return {"file": filename, "status": "Timeout",
                "error": "Server took too long. Try --workers 1 --delay 3.0"}
    except Exception as e:
        return {"file": filename, "status": "Error", "error": str(e)}


def batch_process(folder, max_workers=3, delay=1.0):
    # Support both PDF and DOCX
    pdf_files  = list(Path(folder).glob("*.pdf"))
    docx_files = list(Path(folder).glob("*.docx"))
    all_files  = pdf_files + docx_files

    if not all_files:
        print("❌ No PDF or DOCX files found in: " + folder)
        print("   Make sure your resumes are .pdf or .docx files")
        return

    print("\n" + "="*55)
    print("   AGI CAREER SYSTEM — Batch Processor")
    print("="*55)
    print(f"📁 Folder:        {folder}")
    print(f"📄 Resumes found: {len(all_files)} ({len(pdf_files)} PDF, {len(docx_files)} DOCX)")
    print(f"⚡ Workers:       {max_workers}")
    print(f"⏱  Delay:         {delay}s between uploads")
    print(f"ℹ️  Mode:          Fast — interview links returned INSTANTLY")
    print(f"                  Google Sheet updates in ~30s per resume")
    print("="*55 + "\n")

    results      = []
    success_count = 0
    error_count   = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(upload_resume, str(f)): f for f in all_files}

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)

            status = result.get("status", "")
            if status == "Success":
                success_count += 1
                print(f"✅ [{i}/{len(all_files)}] {result['file']}")
                print(f"   👤 Candidate : {result['candidate']}")
                print(f"   🎤 Interview : {result['link']}")
                if result.get("note"):
                    print(f"   💡 {result['note']}")
            else:
                error_count += 1
                print(f"❌ [{i}/{len(all_files)}] {result['file']}")
                print(f"   Error: {result.get('error', 'Unknown error')[:120]}")

            print()
            time.sleep(delay)

    print("="*55)
    print(f"✅ Successful : {success_count}")
    print(f"❌ Failed     : {error_count}")
    print(f"📊 Total      : {len(all_files)}")
    print(f"📋 Google Sheet is being updated in the background")
    print("="*55)

    # Save log
    log_path = os.path.join(folder, "batch_log.txt")
    with open(log_path, 'w', encoding='utf-8') as log:
        log.write("AGI Career System — Batch Results\n")
        log.write("="*55 + "\n\n")
        for r in results:
            log.write(f"File:      {r.get('file','')}\n")
            log.write(f"Status:    {r.get('status','')}\n")
            log.write(f"Candidate: {r.get('candidate','')}\n")
            log.write(f"Link:      {r.get('link','')}\n")
            if r.get('error'):
                log.write(f"Error:     {r.get('error','')}\n")
            log.write("-"*40 + "\n")
    print(f"\n📝 Log saved to: {log_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch upload resumes to AGI Career System")
    parser.add_argument('--folder',  default='./resumes',                        help='Folder containing resume files (PDF/DOCX)')
    parser.add_argument('--workers', type=int,   default=1,                      help='Concurrent uploads (keep 1-2 to avoid Groq rate limits)')
    parser.add_argument('--delay',   type=float, default=2.0,                    help='Seconds between uploads')
    parser.add_argument('--url',     default='http://localhost:5000/uploadresume',help='API endpoint URL')
    args = parser.parse_args()

    API_URL = args.url
    batch_process(args.folder, args.workers, args.delay)