"""
remove_random_pages.py
───────────────────────────────────────────────────────────────────────────────
Takes scanned answer-paper PDFs, randomly removes a few pages,
and encodes the removed page numbers into the output filename. (used for testing)

Usage:
    python remove_random_pages.py <input.pdf> [options]

Options:
    --num-remove N      Number of pages to remove (default: 2)
    --output-dir DIR    Directory to save output (default: same as input)
    --seed N            Random seed for reproducibility (optional)

OUTPUT FILENAME EXAMPLE
    StudentA_answers.pdf  →  StudentA_answers_MISSING_p3_p7.pdf

DEPENDENCIES
    pip install pypdf
"""

import argparse
import os
import random
import sys
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("pypdf not found. Install it with:  pip install pypdf")
    sys.exit(1)


def remove_random_pages(
    input_path: Path,
    output_dir: Path,
    rng: random.Random,
    num_remove: int = 2,
) -> Path | None:
    """
    Remove `num_remove` random pages from a PDF and save it with a
    descriptive filename that lists the missing (1-indexed) page numbers.

    Returns the output Path, or None if the file was skipped.
    """
    rng = rng or random.Random()

    reader = PdfReader(str(input_path))
    total_pages = len(reader.pages)

    if total_pages <= num_remove:
        print(
            f"  ⚠  Skipping '{input_path.name}': only {total_pages} page(s), "
            f"can't remove {num_remove}."
        )
        return None

    # Pick pages to remove (0-indexed internally)
    removed_indices = sorted(rng.sample(range(total_pages), num_remove))
    removed_pages_1indexed = [i + 1 for i in removed_indices]   # human-readable

    # Build the output PDF
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i not in removed_indices:
            writer.add_page(page)

    # Encode missing pages in the filename
    missing_tag = "_".join(f"p{n}" for n in removed_pages_1indexed)
    stem = input_path.stem
    new_name = f"{stem}_MISSING_{missing_tag}.pdf"
    output_path = output_dir / new_name

    with open(output_path, "wb") as f:
        writer.write(f)

    kept = total_pages - num_remove
    print(
        f"  ✓  {input_path.name}  →  {new_name}\n"
        f"     Removed page(s): {removed_pages_1indexed}  |  "
        f"Kept {kept}/{total_pages} pages"
    )
    return output_path

def parse_args():
    parser = argparse.ArgumentParser(
        description="Randomly remove pages from scanned answer PDFs and "
                    "record missing pages in the filename."
    )
    parser.add_argument(
        "input",
        help="Path to a single PDF file OR a directory containing PDF files.",
    )
    parser.add_argument(
        "--num-remove", "-n",
        type=int,
        default=2,
        metavar="N",
        help="Number of pages to remove per PDF (default: 2).",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        metavar="DIR",
        help="Directory to write output PDFs (default: same as input file/folder).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (optional).",
    )
    return parser.parse_args()

def main():
    args = parse_args()

    input_path = Path(args.input)
    rng = random.Random(args.seed)

    # Collect PDF files to process
    if input_path.is_dir():
        pdf_files = sorted(input_path.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in '{input_path}'.")
            sys.exit(1)
        default_output_dir = input_path
    elif input_path.is_file() and input_path.suffix.lower() == ".pdf":
        pdf_files = [input_path]
        default_output_dir = input_path.parent
    else:
        print(f"Error: '{input_path}' is not a PDF file or a directory.")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nProcessing {len(pdf_files)} file(s) → output dir: {output_dir}\n")

    success, skipped = 0, 0
    for pdf in pdf_files:
        result = remove_random_pages(pdf, output_dir, rng, args.num_remove)
        if result:
            success += 1
        else:
            skipped += 1

    print(f"\nDone. {success} processed, {skipped} skipped.")

if __name__ == "__main__":
    main()