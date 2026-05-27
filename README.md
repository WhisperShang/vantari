# Vantari

Supplements student exam PDFs with missing pages drawn from a fully-scanned blank (empty) exam.

## How it works

Vantari uses ORB feature matching to identify which pages of a student's scanned exam correspond 
to pages in the blank exam. Any blank pages that have no matching student page are automatically 
inserted back in the correct position. The student PDF is supplemented in-place.

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

Run `vantari --help` for all options, including:

- `--verbose` / `-v` - print per-page matching details
- `--dry-run` / `-d` - analyse and report only, without modifying any files
- `--disable-marker` - dont mark supplemented PDFs with a completion marker
- `--dpi`, `--features`, `--lowe`, `--thresh` — tune the ORB matching parameters