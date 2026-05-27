"""
vantari.py
───────────────────────────────────────────────────────────────────────────────
Supplements student exam PDFs with missing pages drawn from a fully-scanned blank (empty) exam.

HOW IT WORKS
    1.  Load the blank exam PDF and extract a visual fingerprint for each page. (excluding annotations)
    2.  For each student PDF:
        - Match each blank page to its corresponding student page.
            - Matches below a minimum score threshold are discarded.
            - If multiple blank pages compete for the same student page,
              the highest scoring match wins.
        - Insert any unmatched blank pages into the student PDF at the
          correct position, and save in-place.

CODE STRUCTURE
    main()
    ├── parses args
    ├── opens blank_doc
    ├── computes blank_descriptors
    └── for each student:
        └── supplement_pdf()
            ├── compute_descriptors()
            ├── build_mapping()
            |   └── match_score()
            └── insert_missing_pages()

FUTURE PLANS
    1.  Page masking — ignore areas where students write and focus matching on 
        fixed content (headers, questions, etc.)
    1.5 ML-assisted mask generation
    2.  Interactive conflict resolution — prompt the user when pages can't be matched confidently
    3.  Auto-tuning of ORB and matching parameters based on user feedback
"""

# ── Imports ──────────────────────────────────────────────────────────────────

import argparse
from pathlib import Path
import sys

try:
    import cv2 as cv
    import fitz
    import numpy as np
except ImportError as e:
    sys.exit(f"Error: missing dependency — {e}. Run 'pip install -e .' to install.")

# ── Type Aliases ─────────────────────────────────────────────────────────────

type MappingList = list[int | None]
type PageDescriptors = np.ndarray
type DocumentDescriptors = list[PageDescriptors]

# ── Tuneable Constants ───────────────────────────────────────────────────────

DPI                   = 150    # render resolution (higher = more accurate but slower)
ORB_FEATURES          = 1000   # max ORB keypoints per page
LOWE_RATIO            = 0.75   # ratio-test threshold (lower = stricter)
MATCH_SCORE_THRESHOLD = 0.30   # fraction of max possible descriptor matches needed

# ── Constants ────────────────────────────────────────────────────────────────

KNN_K               = 2      # must be 2 — Lowe's ratio test compares closest vs second closest
SUPPLEMENT_MARKER   = "✔"   # appended to filename to indicate supplemented files
DESCRIPTION         =  (
    "Supplements student exam PDFs with missing pages drawn from a fully-scanned blank (empty) exam.")
EPILOG              = """\
USAGE
    vantari blank.pdf                     # uses blank's directory
    vantari blank.pdf ./students/         # explicit directory
    vantari blank.pdf a.pdf b.pdf         # explicit files
    vantari blank.pdf a.pdf ./students/   # mix and match
"""

# ── Helpers ──────────────────────────────────────────────────────────────────

def compute_descriptors(
    doc: fitz.Document, 
    dpi: int = DPI, 
    n_features: int = ORB_FEATURES,
    ) -> DocumentDescriptors:

    """
    Render every page of a PDF to a grayscale numpy array and return ORB descriptors for each page.
    
    Args:
        doc:        the opened PDF document to process
        dpi:        render resolution — higher is more accurate but slower
        n_features: max ORB keypoints per page

    Returns:
        list of descriptor arrays, one per page, each of shape (n_keypoints, 32)
    """

    document_descriptors: DocumentDescriptors = []
    orb = cv.ORB_create(nfeatures=n_features)
    
    for page in doc:
        img = cv.cvtColor(page.get_pixmap(dpi=dpi).to_numpy(), cv.COLOR_RGB2GRAY)  # pyright: ignore[reportAttributeAccessIssue]
        page_descriptors = orb.detectAndCompute(img, None)[1]
        document_descriptors.append(page_descriptors or np.empty([KNN_K, 32], dtype=np.uint8))

    return document_descriptors

def match_score(
    blank_desciptors: PageDescriptors,
    student_descriptors: PageDescriptors,
    ) -> int:

    """
    Count how many blank page descriptors are found in the student page.
    Query direction is blank → student to treat blank descriptors as the subset to look for.

    Args:
        blank_desciptors:       ORB descriptors for a single blank page
        student_descriptors:    ORB descriptors for a single student page

    Returns:
        number of good matches found
    """

    bf = cv.BFMatcher_create(cv.NORM_HAMMING)
    raw = bf.knnMatch(blank_desciptors, student_descriptors, k=KNN_K)
    return sum(1 for m, n in raw if m.distance < LOWE_RATIO * n.distance)

def build_mapping(
    blank_document_descriptors:      DocumentDescriptors,
    student_document_descriptors:    DocumentDescriptors,
    verbose: bool = False,
    ) -> MappingList:
    
    """
    Match each blank page to its corresponding student page using ORB descriptors.

    Args:
        blank_document_descriptors:   ORB descriptors for each blank page
        student_document_descriptors: ORB descriptors for each student page
        verbose:                      whether to print progress information

    Returns:
        list of length len(blank_document_descriptors) where each entry is the matching
        student page index, or None if no match was found
    """

    best_blank_per_student: dict[int, tuple[int, int]] = {}  # student_index -> (blank_index, score)

    for blank_index, blank_page_descriptors in enumerate(blank_document_descriptors):
        # Calculate the best matching student page for this blank page
        scores = [match_score(blank_page_descriptors, student_page_descriptors) 
                  for student_page_descriptors in student_document_descriptors]
        best_student_index, best_score = max(enumerate(scores), key=lambda x: x[1])

        # Exclude weak matches
        if best_score < MATCH_SCORE_THRESHOLD * ORB_FEATURES:
            continue

        # Update the best match for this student page if it's better than any previous match (handle conflicts)
        if best_student_index not in best_blank_per_student or best_score > best_blank_per_student[best_student_index][1]:
            best_blank_per_student[best_student_index] = (blank_index, best_score)

    blank_to_student: MappingList = [None] * len(blank_document_descriptors) # blank_index -> student_index

    for student_index, (blank_index, _) in best_blank_per_student.items():
        blank_to_student[blank_index] = student_index

        if verbose:
            score = best_blank_per_student[student_index][1]
            print(f"    Student page {student_index} -> Blank page {blank_index} (score: {score})")

    return blank_to_student

def insert_missing_pages(
    blank_doc: fitz.Document,
    student_doc: fitz.Document,
    blank_to_student: MappingList,
    dry_run: bool = False,
    ) -> list[int]:
    
    """
    Insert missing blank pages into the student PDF in-place (right aligned).

    Args:
        blank_doc:          the opened blank exam PDF to pull missing pages from
        student_doc:        the opened student PDF document to modify
        blank_to_student:   mapping of blank page index → student page index (None if missing)

    Returns:
        list of indices where new pages were inserted
    """
    
    # Precompute the next student page index for each missing page (used to determine insert position)
    next_student: MappingList = [None] * len(blank_to_student)
    last_seen = None
    for blank_index, student_index in reversed(list(enumerate(blank_to_student))):
        last_seen = student_index or last_seen
        if student_index is None:
            next_student[blank_index] = last_seen
    
    # Insert missing pages into the student doc, offsetting position by pages already added
    inserted_indices  = []
    for blank_index, student_index in enumerate(blank_to_student):
        if student_index is None:
            insert_position = (next_student[blank_index] or len(student_doc)) + len(inserted_indices )
            if not dry_run:
                student_doc.insert_pdf(blank_doc, from_page=blank_index, to_page=blank_index, start_at=insert_position)
            inserted_indices .append(insert_position)

    return inserted_indices 

def supplement_pdf(
    student_path: Path,
    blank_doc: fitz.Document, 
    blank_descriptors: DocumentDescriptors,
    verbose: bool = False,
    dry_run: bool = False,
    mark: bool = True,
    ) -> int:

    """
    Supplement a single student PDF in-place with missing pages from the blank exam.

    Args:
        student_path:      path to the student PDF to modify
        blank_descriptors: ORB descriptors for each page of the blank exam
        blank_doc:         the opened blank exam PDF to pull missing pages from

    Returns:
        number of pages inserted
    """
    print(f"\n{'─'*60}\n")
    print(f"Processing: {student_path.name}\n")

    with fitz.open(str(student_path)) as student_doc:
        if verbose:
            print(f"↳ {len(blank_doc)} blank pages -> {len(student_doc)} student pages")

        blank_to_student        = build_mapping(blank_descriptors, compute_descriptors(student_doc), verbose)
        inserted_indices = insert_missing_pages(blank_doc, student_doc, blank_to_student, dry_run)
        student_doc.save(str(student_path))

        missing = sorted(i for i, v in enumerate(blank_to_student) if v is None)
        pages_inserted = len(inserted_indices)
        print()
        if pages_inserted == 0:
            print("✔ Already complete")
        elif pages_inserted == 1:
            print(f"✔ 1 missing page inserted (blank page {missing[0]}) at position: {inserted_indices[0]}")
        else:
            print(f"✔ {pages_inserted} missing pages inserted (blank pages: {', '.join(str(i) for i in missing)}) "
                  f"at positions: {', '.join(str(i) for i in inserted_indices)}")

        if dry_run and pages_inserted > 0:
            print("ℹ Dry run mode enabled — no changes made.")
            if mark:
                new_path = student_path.with_stem(f"{student_path.stem} {SUPPLEMENT_MARKER}")
                student_path.rename(new_path)


        return pages_inserted

def collect_student_paths(
    targets: list[str | Path], 
    blank_path: Path,
    ) -> list[Path]:
    
    """
    Collect and validate student PDF paths from the provided targets
    (files or directories), excluding the blank exam.

    Args:
        targets:    list of file or directory paths to search for student PDFs
        blank_path: path to the blank exam PDF to exclude from results

    Returns:
        list of resolved Paths to student PDF files
    """
    
    seen = set()
    student_paths = []
    for s in targets:
        p = Path(s).resolve()
        if p.is_dir():
            candidates = sorted(f for f in p.glob("*.pdf") if f.resolve() != blank_path)
        elif p.is_file():
            candidates = [p]
        else:
            sys.exit(f"Error: not a file or directory: {p}")

        for c in candidates:
            if c not in seen and c != blank_path:
                seen.add(c)
                student_paths.append(c)

    return student_paths

# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "blank",
        metavar="BLANK_EXAM.pdf",
        help="Path to the fully-scanned blank (empty) exam PDF.",
    )
    parser.add_argument(
        "students",
        nargs="*",
        metavar="STUDENT_OR_DIR",
        help="One or more student PDF files or a directory of PDFs to process.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DPI,
        help=f"Render resolution in DPI (default: {DPI}). Higher = more accurate but slower.",
    )
    parser.add_argument(
        "--features",
        type=int,
        default=ORB_FEATURES,
        help=f"Max ORB keypoints per page (default: {ORB_FEATURES}).",
    )
    parser.add_argument(
        "--lowe",
        type=float,
        default=LOWE_RATIO,
        help=f"Lowe ratio-test threshold (default: {LOWE_RATIO}).",
    )
    parser.add_argument(
        "--match", "-m",
        type=float,
        default=MATCH_SCORE_THRESHOLD,
        help=f"Matching score threshold (default: {MATCH_SCORE_THRESHOLD}).",
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Analyse and report only — do not modify any files.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-page matching details.",
    )
    parser.add_argument(
        "--disable-marker",
        action="store_true",
        default=False,
        help="Do not mark supplemented PDFs with a completion marker.",
    )
    return parser.parse_args()

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    # Override defaults with any CLI-supplied values
    global DPI, ORB_FEATURES, LOWE_RATIO, MATCH_SCORE_THRESHOLD
    DPI           = args.dpi
    ORB_FEATURES  = args.features
    LOWE_RATIO    = args.lowe
    MATCH_SCORE_THRESHOLD = args.match

    # Get blank exam path and validate
    blank_path = Path(args.blank).resolve()
    if not blank_path.is_file():
        sys.exit(f"Error: blank exam not found: {blank_path}")

    # Get student exam paths and validate
    targets: list[str | Path] = args.students or [blank_path.parent]
    student_paths = collect_student_paths(targets, blank_path)
    if not student_paths:
        sys.exit("Error: no student found.")

    # Print configuration summary
    print(f"Blank exam   : {blank_path}")
    print(f"Student files: {len(student_paths)}")
    print(f"DPI          : {DPI}")
    print(f"ORB features : {ORB_FEATURES}")
    print(f"Lowe ratio   : {LOWE_RATIO}")
    print(f"Match thresh. : {MATCH_SCORE_THRESHOLD}")
    if args.dry_run:
        print("Mode         : DRY RUN (no files will be modified)")

    # Process each student exam
    with fitz.open(str(blank_path)) as blank_doc:
        blank_descriptors = compute_descriptors(blank_doc)
        total_inserted = 0

        for student_path in student_paths:
            if not student_path.is_file():
                print(f"\n⚠  File not found, skipping: {student_path}")
                continue
            
            total_inserted += supplement_pdf(
                student_path, blank_doc, blank_descriptors, 
                verbose=args.verbose, 
                dry_run=args.dry_run,
                mark=not args.disable_marker)

    print(f"\n{'═'*60}")
    print(f"Done.  Total pages inserted across all students: {total_inserted}")
    if args.dry_run:
        print("(Dry-run — no files were modified.)")


if __name__ == "__main__":
    main()
