# Vantari

Supplements student exam PDFs with missing pages drawn from a fully-scanned blank (empty) exam.

## How it works

1. Load the blank exam PDF → render every page to an image → extract ORB descriptors for each page (these become the "fingerprints").
2. For each student PDF, render every page and match it against every blank page using BFMatcher + ratio test. The blank page whose descriptors best match a student page is assigned as that page's identity (position in the exam).
3. Any blank pages with no matching student page are inserted into the student PDF in the correct position, and the result is saved in-place.

## Installation

```bash
git clone https://github.com/WhimperShang/vantari.git
cd vantari
pip install -e .
```

## Usage

```bash
vantari blank.pdf                     # uses blank's directory
vantari blank.pdf ./students/         # explicit directory
vantari blank.pdf a.pdf b.pdf         # explicit files
vantari blank.pdf a.pdf ./students/   # mix and match
```

Run `vantari --help` for all options (e.g. `--dry-run`, `--verbose`, and ORB/matching parameters).

## Roadmap

- [ ] Page masking — ignore areas where students write and focus matching on fixed content (headers, questions, etc.)
- [ ] ML-assisted mask generation
- [ ] Interactive conflict resolution — prompt the user when pages can't be matched confidently
- [ ] Auto-tuning of ORB and matching parameters based on user feedback