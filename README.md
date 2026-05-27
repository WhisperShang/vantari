vantari.py
───────────────────────────────────────────────────────────────────────────────
Supplements student exam PDFs with missing pages drawn from a fully-scanned blank (empty) exam.

HOW IT WORKS
    1.  Load the blank exam PDF → render every page to an image → extract ORB
        descriptors for each page (these become the "fingerprints").
    2.  For each student PDF, render every page and match it against every blank
        page using BFMatcher + ratio test. The blank page whose descriptors best
        match a student page is assigned as that page's identity (position in the exam).
    3.  Any blank pages with no matching student page are inserted into the student
        PDF in the correct position, and the result is saved in-place.

USAGE
    python vantari.py blank.pdf                     # uses blank's directory
    python vantari.py blank.pdf ./students/         # explicit directory
    python vantari.py blank.pdf a.pdf b.pdf         # explicit files
    python vantari.py blank.pdf a.pdf ./students/   # or mix and match

    Run with --help for all options. (e.g. --dry-run, --verbose, and ORB/matching parameters)

DEPENDENCIES
    pip install opencv-python-headless pymupdf numpy

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

FUTURE IMPROVEMENTS
    1.  add functionality for drawing a mask over the blank pages to ignore places where students
    |   write and look at only the "fixed" parts of the page (e.g. headers, question, etc.) for matching.
    └──── add machine learning functionality to automatically build the mask
    2.  add light machine learning to ask the user what to do when something unexpected happens
        (e.g. multiple student pages match the same blank page, or an extra page was consistently found in
        all student scans, but isnt in the blank exam).
    3.  add machine learning to tune the ORB and matching parameters based on user feedback for difficult cases
"""
