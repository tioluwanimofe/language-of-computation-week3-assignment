"""Load a books CSV file into books.db, following the rules in rules.md.

Usage:
    python ingest.py books.csv

books.db and ingestion-log.json are created next to this script.
No AI and no internet: the same file always gives the same result.
"""

import csv
import json
import os
import re
import sqlite3
import sys
import traceback
from datetime import datetime
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "books.db")
LOG_PATH = os.path.join(HERE, "ingestion-log.json")

COLUMNS = [
    "book_id", "goodreads_book_id", "best_book_id", "work_id", "books_count",
    "isbn", "isbn13", "authors", "original_publication_year", "original_title",
    "title", "language_code", "average_rating", "ratings_count",
    "work_ratings_count", "work_text_reviews_count", "ratings_1", "ratings_2",
    "ratings_3", "ratings_4", "ratings_5", "image_url", "small_image_url",
]
# Every column except the two ISBN columns is stored exactly as it appears (rules intro).
OTHER_COLUMNS = [c for c in COLUMNS if c not in ("book_id", "isbn", "isbn13")]

# What the reader should do, by reason (rule 7).
ACTIONS = {
    "isbn_mismatch": "Ask the supplier which ISBN is correct, fix the file, and run it again.",
    "isbn_taken": "Check both books; ask the supplier for the correct ISBN.",
    "broken_isbn10": "Ask the supplier for the correct ISBN.",
    "no_isbn": "Find the ISBN, if the book has one.",
    "isbn13_dropped": "Check the edition with the supplier if the ISBN-13 matters.",
    "isbn13_in_isbn10_column": "No action needed; review if in doubt.",
    "chopped_isbn13": "No action needed; review if in doubt.",
    "stored_isbn_kept": "No action needed.",
    "isbn_changed": "Confirm the new ISBN is right.",
    "broken_row": "Fix the row in the file and run it again.",
    "already_exists": "No action needed.",
}


# ---------- ISBN helpers (Definitions) ----------

def is_valid_isbn10(s):
    if not re.fullmatch(r"\d{9}[\dX]", s):
        return False
    total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(s))
    return total % 11 == 0


def is_valid_isbn13(s):
    if not re.fullmatch(r"97[89]\d{10}", s):
        return False
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(s))
    return total % 10 == 0


def isbn13_check_digit(first12):
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(first12))
    return str((10 - total % 10) % 10)


def isbn10_to_isbn13(isbn10):
    first12 = "978" + isbn10[:9]
    return first12 + isbn13_check_digit(first12)


def isbn13_to_isbn10(isbn13):
    """Only for ISBN-13s that start with 978; a 979 ISBN-13 has no ISBN-10."""
    if not isbn13.startswith("978"):
        return None
    first9 = isbn13[3:12]
    total = sum((10 - i) * int(c) for i, c in enumerate(first9))
    check = (11 - total % 11) % 11
    return first9 + ("X" if check == 10 else str(check))


SCIENTIFIC = re.compile(r"\d(\.\d+)?[eE]\+\d+")


def scientific_agrees(isbn13, raw):
    """Rule 2.2: agrees if the ISBN-13 differs from the scientific value by 5 or less."""
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return False
    return abs(Decimal(isbn13) - value) <= 5


# ---------- Rules 1-3: decide the final ISBNs for one row ----------

def decide_isbns(raw10, raw13):
    """Returns (isbn10, isbn13, warnings, reject_reason).

    warnings is a list of (code, message); reject_reason is (code, message) or None.
    """
    warnings = []
    final10 = None
    final13 = None
    from_isbn_column13 = None  # an ISBN-13 found in the isbn column (rules 1.4 and 1.5)

    # What kind of value is in the isbn13 column?
    if raw13 == "":
        kind13 = "empty"
    elif is_valid_isbn13(raw13):
        kind13 = "valid"
    elif SCIENTIFIC.fullmatch(raw13):
        kind13 = "scientific"
    else:
        kind13 = "not_isbn"

    def agrees_with_isbn13_column(candidate):
        if kind13 == "valid":
            return candidate == raw13          # answer 2: identical
        if kind13 == "scientific":
            return scientific_agrees(candidate, raw13)
        return False

    # Rule 1: the isbn column
    s = re.sub(r"[\s-]", "", raw10)                     # 1.1
    if s != "":
        if s.endswith("x"):                              # 1.2
            s = s[:-1] + "X"
        if s.isdigit() and len(s) < 10:                  # 1.3
            s = s.zfill(10)

        if is_valid_isbn10(s):
            final10 = s
        elif is_valid_isbn13(s):                         # 1.4
            if kind13 == "valid" and raw13 != s:         # answer 1
                warnings.append(("isbn13_in_isbn10_column",
                                 f"isbn column held ISBN-13 {s}, different from the isbn13 column; "
                                 f"kept the isbn13 column's value and dropped {s}"))
            else:
                from_isbn_column13 = s
                warnings.append(("isbn13_in_isbn10_column",
                                 f"isbn column held a valid ISBN-13 ({s}); used it as the ISBN-13"))
        elif (re.fullmatch(r"\d{10}", s) and is_valid_isbn13("978" + s)
              and agrees_with_isbn13_column("978" + s)):  # 1.5
            from_isbn_column13 = "978" + s
            warnings.append(("chopped_isbn13",
                             f"isbn {raw10!r} is an ISBN-13 with 978 cut off; "
                             f"repaired to {from_isbn_column13} (agrees with the isbn13 column)"))
        else:                                            # 1.6
            if re.search(r"[^\dX]", s):
                why = "illegal character"
            elif len(s) != 10:
                why = "wrong length"
            else:
                why = "bad check digit"
            warnings.append(("broken_isbn10", f"isbn {raw10!r} dropped: {why}"))
    # 1.7: empty -> no ISBN-10, no warning

    # Rule 2: the isbn13 column
    if from_isbn_column13 is not None:
        final13 = from_isbn_column13
    elif kind13 == "valid":                              # 2.1
        final13 = raw13
        if final10 is not None and isbn10_to_isbn13(final10) != raw13:   # 3.1
            return None, None, warnings, (
                "isbn_mismatch",
                f"isbn {final10} and isbn13 {raw13} are both valid but don't match "
                f"({final10} converts to {isbn10_to_isbn13(final10)})")
    elif kind13 == "scientific":
        if final10 is not None:
            converted = isbn10_to_isbn13(final10)
            if scientific_agrees(converted, raw13):      # 2.2
                final13 = converted
            else:                                        # 2.3
                warnings.append(("isbn13_dropped",
                                 f"isbn13 {raw13!r} disagrees with isbn {final10} "
                                 f"(which converts to {converted}); ISBN-13 dropped"))
        else:                                            # 2.4
            warnings.append(("isbn13_dropped",
                             f"isbn13 {raw13!r} is in scientific notation and there is no valid "
                             f"ISBN-10 to rebuild it from; ISBN-13 dropped"))
    elif kind13 == "not_isbn":                           # 2.5
        warnings.append(("isbn13_dropped", f"isbn13 {raw13!r} is not an ISBN; dropped"))
    else:                                                # 2.6
        if final10 is not None:
            final13 = isbn10_to_isbn13(final10)

    # 2.7: convert the ISBN-10 from a 978 ISBN-13 when there is none
    if final10 is None and final13 is not None:
        final10 = isbn13_to_isbn10(final13)

    # 3.2: no usable ISBN at all
    if final10 is None and final13 is None:
        warnings.append(("no_isbn", "no usable ISBN"))

    return final10, final13, warnings, None


# ---------- Database ----------

def open_db():
    con = sqlite3.connect(DB_PATH)
    cols = ",\n    ".join(f'"{c}" TEXT' for c in OTHER_COLUMNS)
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS books (
            book_id TEXT PRIMARY KEY,
            original_isbn TEXT,
            original_isbn13 TEXT,
            isbn10 TEXT UNIQUE,
            isbn13 TEXT UNIQUE,
            {cols}
        )""")
    return con


def row_detail(row_number, record, reasons):
    return {
        "row": row_number,
        "book_id": record.get("book_id", ""),
        "title": record.get("title", ""),
        "isbn": record.get("isbn", ""),
        "isbn13": record.get("isbn13", ""),
        "reasons": [{"code": code, "reason": msg, "action": ACTIONS[code]} for code, msg in reasons],
    }


def process_file(con, path, entry):
    counts = entry["counts"]
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header != COLUMNS:
            raise ValueError(f"unexpected header in {path}: {header}")

        for row_number, values in enumerate(reader, start=1):     # answer 4
            counts["read"] += 1

            # Answer 6: broken rows are rejected
            if len(values) != len(COLUMNS):
                record = dict(zip(COLUMNS, values))
                counts["rejected"] += 1
                entry["rejected"].append(row_detail(row_number, record, [(
                    "broken_row", f"row has {len(values)} columns, expected {len(COLUMNS)}")]))
                continue
            record = dict(zip(COLUMNS, values))
            book_id = record["book_id"]
            if book_id.strip() == "":
                counts["rejected"] += 1
                entry["rejected"].append(row_detail(row_number, record, [("broken_row", "empty book_id")]))
                continue

            isbn10, isbn13, warnings, reject = decide_isbns(record["isbn"], record["isbn13"])
            if reject:
                counts["rejected"] += 1
                entry["rejected"].append(row_detail(row_number, record, warnings + [reject]))
                continue

            # Rule 5.2 (and answer 8): an ISBN can belong to only one book
            taken_by = con.execute(
                "SELECT book_id, title FROM books WHERE book_id != ? AND "
                "((? IS NOT NULL AND isbn10 = ?) OR (? IS NOT NULL AND isbn13 = ?))",
                (book_id, isbn10, isbn10, isbn13, isbn13)).fetchone()
            if taken_by:
                counts["rejected"] += 1
                entry["rejected"].append(row_detail(row_number, record, warnings + [(
                    "isbn_taken", f"ISBN already belongs to book {taken_by[0]} ({taken_by[1]})")]))
                continue

            stored = con.execute(
                "SELECT original_isbn, original_isbn13, isbn10, isbn13, "
                + ", ".join(f'"{c}"' for c in OTHER_COLUMNS)
                + " FROM books WHERE book_id = ?", (book_id,)).fetchone()

            original_isbn, original_isbn13 = record["isbn"], record["isbn13"]
            others = [record[c] for c in OTHER_COLUMNS]

            if stored is None:
                con.execute(
                    "INSERT INTO books (book_id, original_isbn, original_isbn13, isbn10, isbn13, "
                    + ", ".join(f'"{c}"' for c in OTHER_COLUMNS) + ") VALUES ("
                    + ", ".join("?" * (5 + len(OTHER_COLUMNS))) + ")",
                    [book_id, original_isbn, original_isbn13, isbn10, isbn13] + others)
                counts["loaded"] += 1
                outcome = "loaded"
            else:
                s_orig10, s_orig13, s_isbn10, s_isbn13 = stored[:4]
                s_others = list(stored[4:])

                # Rule 6.3: new row has no usable ISBN but the stored book does
                if isbn10 is None and isbn13 is None and (s_isbn10 is not None or s_isbn13 is not None):
                    warnings = [w for w in warnings if w[0] != "no_isbn"]
                    warnings.append(("stored_isbn_kept",
                                     "new row has no usable ISBN; kept the stored ISBNs"))
                    isbn10, isbn13 = s_isbn10, s_isbn13
                    original_isbn, original_isbn13 = s_orig10, s_orig13   # answer 5
                # Rule 6.4: a different valid ISBN than the stored one
                elif ((isbn10 and s_isbn10 and isbn10 != s_isbn10)
                      or (isbn13 and s_isbn13 and isbn13 != s_isbn13)):
                    warnings.append(("isbn_changed",
                                     f"ISBN changed from {s_isbn10}/{s_isbn13} to {isbn10}/{isbn13}"))

                # Answer 9: compare final values only, not the original ISBN text
                if [isbn10, isbn13] + others == [s_isbn10, s_isbn13] + s_others:
                    counts["skipped"] += 1                                   # 6.1
                    outcome = "skipped"
                    entry["skipped"].append(row_detail(row_number, record, [(
                        "already_exists", "already in the database; nothing changed")]))
                else:
                    con.execute(                                             # 6.2
                        "UPDATE books SET original_isbn = ?, original_isbn13 = ?, isbn10 = ?, isbn13 = ?, "
                        + ", ".join(f'"{c}" = ?' for c in OTHER_COLUMNS) + " WHERE book_id = ?",
                        [original_isbn, original_isbn13, isbn10, isbn13] + others + [book_id])
                    counts["updated"] += 1
                    outcome = "updated"

            if warnings:                                                     # answer 3
                counts["warnings"] += 1
                detail = row_detail(row_number, record, warnings)
                detail["outcome"] = outcome
                entry["warnings"].append(detail)


# ---------- Log ----------

def read_log():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, encoding="utf-8") as f:
        runs = json.load(f)   # if the log is damaged, stop rather than overwrite earlier runs
    if not isinstance(runs, list):
        raise ValueError(f"{LOG_PATH} is not a list of runs; not overwriting it")
    return runs


def append_log(entry):
    runs = read_log()
    runs.append(entry)
    tmp = LOG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2, ensure_ascii=False)
    os.replace(tmp, LOG_PATH)


def main():
    if len(sys.argv) != 2:
        print("Usage: python ingest.py <books csv file>")
        return 2
    path = sys.argv[1]
    read_log()   # check the log is readable before touching the database

    entry = {
        "run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "file": os.path.basename(path),
        "file_path": os.path.abspath(path),
        "finished": False,
        "error": None,
        "counts": {"read": 0, "loaded": 0, "updated": 0, "skipped": 0, "rejected": 0, "warnings": 0},
        "rejected": [],
        "skipped": [],
        "warnings": [],
    }

    con = open_db()
    try:
        with con:   # one transaction: a crash undoes the whole run (answer 7)
            process_file(con, path, entry)
        entry["finished"] = True
    except Exception as e:
        entry["error"] = f"{type(e).__name__}: {e}"
        entry["note"] = "The run did not finish. Nothing from this run was kept in books.db."
        traceback.print_exc()
    finally:
        con.close()
        append_log(entry)

    c = entry["counts"]
    print(f"{entry['file']}: read {c['read']}, loaded {c['loaded']}, updated {c['updated']}, "
          f"skipped {c['skipped']}, rejected {c['rejected']}, rows with warnings {c['warnings']}")
    print("finished" if entry["finished"] else "NOT finished: " + entry["error"])
    print(f"Log written to {LOG_PATH}")
    return 0 if entry["finished"] else 1


if __name__ == "__main__":
    sys.exit(main())
