"""
remove_random_pages.py
───────────────────────────────────────────────────────────────────────────────
Takes scanned answer-paper PDFs, randomly removes a few pages,
and encodes the removed page numbers into the output filename. (used for testing)

USAGE
    python remove_random_pages.py <input.pdf> [options] # for a single file
    python remove_random_pages.py <input_folder> [options] # for all PDFs in a folder

    Run "python remove_random_pages.py --help" for all options, including:

    --num-remove / -n       Number of pages to remove (default: 2)
    --output-dir / -o       Directory to save output (default: same as input)
    --seed / -s             Random seed for reproducibility (optional)

OUTPUT FILENAME EXAMPLE
    StudentA_answers.pdf  →  StudentA_answers_MISSING_p3_p7.pdf

DEPENDENCIES
    pip install pymupdf
"""

# ── Imports ──────────────────────────────────────────────────────────────────

import argparse
import random
import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    print("fitz not found. Install it with:  pip install pymupdf")
    sys.exit(1)

# ── Helpers ──────────────────────────────────────────────────────────────────

def generate_new_name(
    input_path: Path, 
    removed_indices: list[int],
    ) -> str:

    *head, tail = [i + 1 for i in removed_indices]  # convert to 1-based page numbers
    missing_tag = ", ".join(str(n) for n in head) + (f" & {tail}" if head else str(tail))
        
    return f"{input_path.stem} (missing {missing_tag}){input_path.suffix}"

def remove_random_pages(
    input_path: Path,
    output_dir: Path,
    rng: random.Random,
    num_remove: int = 2,
) -> Path | None:
    
    """
    Remove `num_remove` randomly selected pages from a PDF and save it
    with the missing page numbers encoded in the filename.

    Args:
        input_path: Path to the source PDF file.
        output_dir: Directory to write the output PDF.
        rng: Random instance to use for page selection.
        num_remove: Number of pages to remove (default: 2).

    Returns:
        Path to the output PDF, or None if the file was skipped.
    """
    
    with fitz.open(str(input_path)) as doc:
        total_pages = len(doc)

        # Validate that there are enough pages to remove
        if total_pages <= num_remove:
            print(f"⚠ Skipping '{input_path.name}': only {total_pages} page(s), can't remove {num_remove}.")
            return None
        
        # Remove pages in reverse order to avoid index shifting issues
        removed_indices = sorted(rng.sample(range(total_pages), num_remove))
        for i in reversed(removed_indices):
            doc.delete_page(i)

        # Rename output file to include removed page numbers
        new_name = generate_new_name(input_path, removed_indices)
        output_path = output_dir / new_name

        doc.save(str(output_path))
        print(f"✔ Processed '{input_path.name}': saved to {output_path.name}.")

    return output_path

def collect_pdf_paths(
    targets: list[str | Path], 
    ) -> list[Path]:
    
    """
    Collect and validate PDF paths from the provided targets
    (files or directories), avoiding duplicates.

    Args:
        targets:    list of file or directory paths to search for PDFs

    Returns:
        list of resolved Paths to PDF files
    """
    
    seen = set()
    paths = []

    for target in map(Path, targets):
        target = target.resolve()
        if target.is_dir():
            candidates = sorted(target.glob("*.pdf"))
        elif target.is_file() and target.suffix.lower() == ".pdf":
            candidates = [target]
        else:
            sys.exit(f"Error: not a PDF file or directory: {target}")

        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                paths.append(candidate)

    return paths

# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Takes scanned answer-paper PDFs, randomly removes a few pages,"
                    "and encodes the removed page numbers into the output filename. (used for testing)"
    )
    parser.add_argument(
        "input",
        nargs="+",
        help="PDF file(s) and/or directory(ies) to process.",
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
        "--seed", "-s",
        type=int,
        default=None,
        help="Random seed for reproducibility (optional).",
    )
    return parser.parse_args()

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    # Collect pdfs to process
    targets: list[str | Path] = args.input or [Path.cwd()]
    pdf_paths = collect_pdf_paths(targets)

    # Setup the random generator and output directory
    rng = random.Random(args.seed)
    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nProcessing {len(pdf_paths)} file(s) → output dir: {output_dir}\n")

    processed, skipped = 0, 0
    for path in pdf_paths:
        result = remove_random_pages(path, output_dir, rng, args.num_remove)
        if result:
            processed += 1
        else:
            skipped += 1

    print(f"\n{processed} pdfs processed, {skipped} skipped.")

if __name__ == "__main__":
    main()