# ISBN Data Validation: books.csv and books-batch2.csv

This is a diagnosis only. Neither file was changed and nothing was fixed.

- **books.csv**: 10,000 rows, downloaded from the goodbooks-10k repository.
- **books-batch2.csv**: 31 rows (30 distinct rows plus one exact duplicate), the second delivery.

Every row's `isbn` and `isbn13` value was checked, exactly as it appears in the file (as text, without letting a spreadsheet reinterpret it).

## How "valid" was decided

There are two kinds of ISBN.

**ISBN-10** (used until 2007) has 10 characters: 9 digits plus a check character. The check character is chosen so that, multiplying the characters by 10, 9, 8, ... 1 and adding them up, the total is divisible by 11. Because the remainder can need the value 10, the check character can be `X`, which means 10. Example: `043965548X` is valid.

**ISBN-13** (used since 2007) has 13 digits and starts with `978` or `979`. The digits are multiplied alternately by 1 and 3 and added; the last digit is chosen so that the total is divisible by 10. It is never `X`. Every ISBN-10 has an ISBN-13 form: put `978` in front of its first 9 digits and recompute the check digit. ISBN-13s that start with `979` have no ISBN-10 form.

The last character exists to catch mistakes: a single wrong digit, or two swapped neighbouring digits, makes the check fail. A value that passes the check is *probably* typed correctly, but the check cannot say which book it belongs to.

In this diagnosis a value is **valid as-is** only if it is exactly 10 characters (`0-9`, with `X` allowed last) passing the ISBN-10 check, or exactly 13 digits passing the ISBN-13 check. Anything else is a problem, described below.

## Summary: books.csv (10,000 rows)

### `isbn` column

| Kind | Rows | Example (book_id: value) | Valid? |
|---|---:|---|---|
| Valid ISBN-10 as-is | 2,690 | 18: `043965548X` | Yes |
| Leading zeros dropped | 6,587 | 1: `439023483` (should be `0439023483`) | No, but the information is still there |
| Empty | 700 | 106 (Bossypants): `` | No value |
| Bad check digit | 23 | 1443: `9380658797` | No |

**Leading zeros dropped (6,587 rows).** The value is 7, 8 or 9 digits long (5,563 have 9 digits, 913 have 8, 111 have 7). Adding zeros at the front to make 10 characters gives a valid ISBN-10 in every one of these rows. *Probable cause:* the column was treated as a number at some point (for example by a spreadsheet or a data library), and numbers don't keep leading zeros. The information is not lost, because an ISBN-10 is always exactly 10 characters, so the number of missing zeros is known.

**Empty (700 rows).** No value at all. *Probable cause:* the source had no ISBN-10 for that edition (e.g. e-book-only or newer editions), or it was never collected. Nothing can be recovered from this column; 135 of these rows still have something in `isbn13`.

**Bad check digit (23 rows).** 9 of these are 10 digits long and 14 are shorter (zero-padding them still fails the check). For 20 of the 23, putting `978` in front of the zero-padded value gives a valid ISBN-13, and that matches the book's `isbn13` column: e.g. book 1443 `9380658797` is really the end of the ISBN-13 `9789380658797`. *Probable cause:* someone filled the ISBN-10 column by chopping the `978` off an ISBN-13, which keeps the wrong check digit (ISBN-13 and ISBN-10 check digits are computed differently). The remaining 3 (book 916 `812971060`, book 4322 `1400139027`, book 8552 `84386874`) have no explanation: probably a typo, and the correct value cannot be worked out from this column alone.

### `isbn13` column

| Kind | Rows | Example (book_id: value) | Valid? |
|---|---:|---|---|
| Scientific notation | 9,407 | 1: `9.78043902348e+12` | No, the last digit is lost |
| Empty | 585 | 106 (Bossypants): `` | No value |
| Not an ISBN (other number stored as decimal) | 8 | 958: `76783609419.0` | No |
| Valid ISBN-13 as text | 0 | – | – |

**Scientific notation (9,407 rows).** The 13-digit number was stored as a floating-point number and written out with only 12 significant digits, e.g. `9780439023483` became `9.78043902348e+12`. Trailing zeros are also cut, e.g. book 11 `9.78159448e+12`. *Probable cause:* the column was read as a number and saved back to text. **The 13th digit (the check digit) is lost** and the 12th may have been rounded up. The value on its own can no longer be validated. It can only be rebuilt from the `isbn` column:
- 9,238 rows: the rebuilt ISBN-13 from the `isbn` column agrees with the scientific-notation value.
- 13 rows: they disagree, e.g. book 622 has `isbn` `446612707` but `isbn13` `9.78055381395e+12`. The two columns probably describe different editions, so there is no way to tell which is right.
- 156 rows: the `isbn` column is empty or bad, so the lost digit can't be rebuilt from it.

**Empty (585 rows).** No value. 20 of these rows still have something in `isbn`. **565 rows have both columns empty**, so they have no ISBN at all.

**Not an ISBN (8 rows).** Values such as `76783609419.0`, `6.45573003012e+11`, `25986247522.0` are 11–12 digit numbers that don't start with 978/979. They look like product barcodes (UPC codes, which also lost a leading zero) put in the ISBN-13 column. Two are different: book 1443 `97893806587.0` is an ISBN-13 that lost its last two digits, and book 8174 `195170342.0` is the ISBN-10 (`0195170342`) placed in the wrong column. *Probable cause:* the supplier used whatever code it had for the product, and it went through the same number conversion.

### Duplicates in books.csv

No duplicate `book_id`s, no duplicate rows, and no two rows share the same ISBN-10.

## Summary: books-batch2.csv (31 rows)

This file uses the same columns. 16 rows are books already in books.csv (same `book_id`); 15 rows are new books (14 distinct book_ids, 10001–10014, with 10001 appearing twice).

### `isbn` column

| Kind | Rows | Example (book_id: value) | Valid? |
|---|---:|---|---|
| Valid ISBN-10 as-is | 12 | 24: `0439139600` | Yes |
| Leading zeros dropped | 7 | 2: `439554934` | No, information still there |
| Empty | 5 | 10006: `` | No value |
| Hyphens or spaces | 2 | 10002: `0-450-19827-8`; 10003: `" 162 001 4750 "` | No, but valid once the hyphens/spaces are removed |
| Lowercase `x` | 1 | 10004: `031200009x` | No, but valid if read as `X` |
| ISBN-13 in the ISBN-10 column | 1 | 10014: `9781982147600` | A valid ISBN-13, in the wrong column |
| Illegal character | 1 | 10008: `04390A3483` | No |
| Too long (11 digits) | 1 | 10009: `15287463097` | No |
| Bad check digit | 1 | 10007: `1854433017` | No |

New kinds of problem that do not occur in books.csv:

- **Hyphens or spaces.** ISBNs are often printed with hyphens between their parts, and the supplier copied them that way. The value in 10003 also has spaces at both ends. Removing them gives a valid ISBN-10; no information is lost.
- **Lowercase `x`.** Typed by hand. `X` and `x` mean the same thing; the value is valid if read case-insensitively.
- **ISBN-13 in the ISBN-10 column.** The value is a correct ISBN-13 and the `isbn13` column is empty, so it was probably entered in the wrong field. No information is lost.
- **Illegal character.** `04390A3483` contains the letter `A`, which can never appear in an ISBN. *Probable cause:* a typo or bad scan. If the `A` were a `2`, it would be `0439023483`, which is the ISBN of *The Hunger Games*, not *The Glass Aviary*. So the original value is lost, and any repair would be a guess.
- **Too long.** `15287463097` is 11 digits. Its first 10 digits are `1528746309`, the ISBN of *The Lantern Keeper's Daughter*, not *Borrowed Light*. Probably a copy-paste error; the correct value is lost.
- **Bad check digit.** `1854433017` (*Small Hours*) has the right length but fails the check, and there is no `isbn13` to compare with. Probably a mistyped digit; we can't tell which.

### `isbn13` column

| Kind | Rows | Example (book_id: value) | Valid? |
|---|---:|---|---|
| Scientific notation | 14 | 132: `9.78140130858e+12` | No, last digit lost (all 14 agree with their `isbn`) |
| Valid ISBN-13 (978) | 8 | 24: `9780439139601` | Yes |
| Valid ISBN-13 (979) | 1 | 10006: `9798351220413` | Yes, and it has no ISBN-10 form |
| Empty | 8 | 10007: `` | No value |

So batch2 mixes two formats: the 16 older books mostly come in the same broken form as books.csv, while the new books mostly have ISBN-13s written correctly as text.

### Rows where the two columns or rows disagree

| book_id | Title | Problem |
|---|---|---|
| 10011 | Tides of Marrow Bay | `isbn` `1555550126` and `isbn13` `9781555550134` are each valid, but they don't match. The ISBN-10 converts to `9781555550127`. One of them is wrong, and the data can't say which. |
| 10013 | Paper Moons | `isbn` `1416524797` is valid but is already the ISBN of book 9, *Angels & Demons*, in both files. Two different books claim the same ISBN. |
| 10001 | The Lantern Keeper's Daughter | Appears twice, as two identical rows. |
| 10010 | Untitled Manuscript (author "Unknown") | Both ISBN columns empty. |
| 106, 25 | Bossypants, Deathly Hallows | Both ISBN columns empty. Book 25 **had** ISBNs in books.csv (`545010225` / `9.78054501022e+12`); in batch2 they are blank. |

### Books that arrive again with changes

Compared with books.csv by `book_id`:

- **Same values, nothing changed:** 10 books (e.g. 1, 2, 3, 106).
- **Only the ISBN formatting changed:** book 24 (*Goblet of Fire*) goes from `439139600` / `9.7804391396e+12` to `0439139600` / `9780439139601`. Same ISBN, now written correctly.
- **ISBNs removed:** book 25 (*Deathly Hallows*), described above.
- **Ratings changed:** books 132, 14, 13 and 134 have higher `ratings_count`, `work_ratings_count` and `ratings_5`. These look like normal updates a week later.

## What this means before loading

- About two thirds of books.csv has ISBN-10s that are damaged only in format (lost zeros). Almost all ISBN-13s in books.csv are damaged in a way that loses the check digit, and can only be rebuilt from the ISBN-10.
- Some damage loses information: illegal characters, extra digits, bad check digits, and columns that contradict each other. A "fix" for these would be a guess.
- About 6% of books (565 in books.csv, 3 in batch2) have no ISBN at all.
- ISBNs are not perfectly unique in the data (Paper Moons vs Angels & Demons), and the same `book_id` can arrive twice or arrive again with different values.

These are the decisions rules.md needs to make.
