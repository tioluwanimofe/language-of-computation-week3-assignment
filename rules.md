# Rules for loading books

These rules decide what happens to every row of a books CSV file. Only the `isbn` and `isbn13` columns are checked. Every other column is loaded exactly as it appears in the file.

## Definitions

- A **valid ISBN-10** is exactly 10 characters: 9 digits followed by a digit or a capital `X`, passing the ISBN-10 check (weights 10 down to 1, total divisible by 11).
- A **valid ISBN-13** is exactly 13 digits starting with `978` or `979`, passing the ISBN-13 check (weights 1,3,1,3..., total divisible by 10).
- **Converting** a valid ISBN-10 to ISBN-13: `978` + its first 9 digits + a newly calculated ISBN-13 check digit.
- **Converting** a valid ISBN-13 that starts with `978` to ISBN-10: its digits 4–12 + a newly calculated ISBN-10 check character. A `979` ISBN-13 has no ISBN-10 and is never converted.
- A **warning** means the row is loaded, but the run's log lists the row and the reason so a person can review it.
- A **rejected** row is not loaded at all; the log lists it with the reason.

## 1. Fixing the ISBN-10 column (`isbn`)

The steps are applied in this order. A repair is only kept if the result is a valid ISBN-10; otherwise the value is treated as broken (rule 1.6).

1. **Spaces and hyphens:** remove every space and hyphen, including at the ends. *Why:* they are formatting, not information.
2. **Lowercase x:** change a lowercase `x` in the last position to `X`. *Why:* `x` and `X` mean the same (10). Deleting it would remove the check character.
3. **Lost leading zeros:** if the value is only digits and shorter than 10 characters, add zeros on the left until it is 10 characters. *Why:* the column was treated as a number, which drops leading zeros. Every ISBN-10 is exactly 10 characters, so the number of missing zeros is known. This is not a guess.
4. **ISBN-13 in the ISBN-10 column:** if the value is a valid ISBN-13, it is used as the book's ISBN-13 (if the `isbn13` column doesn't already hold a different valid one), the ISBN-10 is converted from it, and the row gets a warning. *Why:* the value is correct, just in the wrong column.
5. **Chopped ISBN-13:** if the value (after step 3) fails the ISBN-10 check, but `978` + the value is a valid ISBN-13 *and* that ISBN-13 agrees with the `isbn13` column (rule 2.2), use that ISBN-13, convert the ISBN-10 from it, and give a warning. *Why:* two independent columns agree, so this is strong evidence, not a guess. If the `isbn13` column doesn't agree, it is a guess, and rule 1.6 applies.
6. **Broken (illegal character, wrong length, bad check digit):** the value is dropped (the book has no ISBN-10) and the row gets a warning. *Why:* the real digits are lost; any "repair" would be a guess and could point to a different book (e.g. `04390A3483` with the `A` read as `2` is The Hunger Games).
7. **Empty:** the book has no ISBN-10 from this column. No warning.

## 2. Fixing the ISBN-13 column (`isbn13`)

1. **Valid ISBN-13 as text:** kept as is.
2. **Scientific notation** (like `9.78043902348e+12`): the last digit is lost, so the value is only used to check agreement. It **agrees** with an ISBN-13 if the ISBN-13 differs from the scientific value's number by 5 or less (this allows for the rounding of the last digit). If the book has a valid ISBN-10, convert it to ISBN-13. If that agrees, store it. *Why:* the ISBN-10 has all the information and the scientific value confirms it.
3. **Scientific notation that disagrees with a valid ISBN-10:** drop the ISBN-13, keep only the ISBN-10, and give a warning. *Why:* the two columns probably describe different editions; we can't tell which, and the ISBN-10 is the only complete value.
4. **Scientific notation with no valid ISBN-10:** drop the ISBN-13 and give a warning. *Why:* the check digit is lost and there's nothing to rebuild it from. Adding a digit would be a guess.
5. **Not an ISBN** (anything else, e.g. `76783609419.0`): drop it and give a warning. *Why:* it isn't an ISBN, so it can't be used to identify the book.
6. **Empty:** if the book has a valid ISBN-10, convert it to ISBN-13 (no warning). *Why:* this is calculation, not guessing.
7. If the ISBN-13 is valid and starts with `978` and there is no ISBN-10, convert the ISBN-10 from it. A `979` ISBN-13 is stored with an empty ISBN-10.

## 3. Both columns together

1. **Both valid but they don't match** (the ISBN-10 converted to ISBN-13 isn't the ISBN-13): **reject** the row. *Why:* each is valid on its own, so we can't tell which is wrong, and loading either could attach the wrong ISBN to the book.
2. **No usable ISBN at all** (both empty, or both dropped by the rules above): load the row with no ISBN and a warning. *Why:* the book is still a real book and its `book_id` identifies it; the warning tells someone to find the ISBN.

## 4. What is stored

Each book row stores the original `isbn` and `isbn13` text from the file, exactly as received, **and** the final `isbn10` and `isbn13` after these rules (empty if there are none). *Why:* anyone can see what was repaired and check it.

## 5. What makes two rows the same book

1. Two rows are the same book if they have the same **`book_id`**. *Why:* every row has one, including books with no ISBN.
2. An ISBN can belong to only one book. If a row's final ISBN-10 or ISBN-13 is already stored for a *different* `book_id` (in the database, or earlier in the same file), the row is **rejected**. *Why:* two different books cannot share an ISBN, so one of them is wrong, and the one already loaded came first (e.g. Paper Moons uses the ISBN of Angels & Demons).

## 6. A book that is already in the database arrives again

Compare the new row with the stored book using the **final** values (the repaired ISBNs and every other column), not the original ISBN text.

1. **Nothing changed:** skip it; count it as "skipped (already exists)". *Why:* loading it again would create a duplicate.
2. **Something changed** (e.g. ratings went up): update the stored book with the new values; count it as "updated". *Why:* the newer file is the newer information.
3. **The new row has no usable ISBN but the stored book does** (e.g. Deathly Hallows): keep the stored ISBNs and give a warning. The other columns follow rules 6.1 and 6.2. *Why:* a missing value is not new information, and losing a good ISBN would make the data worse.
4. **The new row has a different valid ISBN than the stored one:** update it (rule 6.2), and give a warning. *Why:* it's newer information, but a changed ISBN is unusual and a person should look at it.
5. The same `book_id` appearing twice in one file is handled the same way: the first row is loaded, and the second is compared with it (an identical copy is skipped).

## 7. What the report must tell the reader

For every run:

- when it ran, which file, and whether it finished;
- how many rows were read, loaded, updated, skipped because they already exist, rejected, and loaded with a warning (read = loaded + updated + skipped + rejected);
- every row that was rejected: its row number in the file, `book_id`, title, the original `isbn` and `isbn13`, the reason, and what to do;
- every row loaded with a warning, with the same details.

What to do, by reason:

| Reason | What the reader should do |
|---|---|
| ISBN-10 and ISBN-13 don't match | Ask the supplier which ISBN is correct, fix the file, and run it again. |
| ISBN already belongs to another book | Check both books; ask the supplier for the correct ISBN. |
| Broken ISBN dropped | Ask the supplier for the correct ISBN. |
| No ISBN | Find the ISBN, if the book has one. |
| ISBN-13 dropped (disagrees, or can't be rebuilt, or not an ISBN) | Check the edition with the supplier if the ISBN-13 matters. |
| ISBN-13 found in the ISBN-10 column, or chopped ISBN-13 repaired | No action needed; review if in doubt. |
| Stored ISBN kept because the new row had none | No action needed. |
| ISBN changed | Confirm the new ISBN is right. |

## 8. Examples

These assume books.csv is loaded first, then books-batch2.csv.

| # | Book | isbn | isbn13 | What happens |
|---|---|---|---|---|
| 1 | 1 The Hunger Games (books.csv) | `439023483` | `9.78043902348e+12` | Zeros added: `0439023483`. ISBN-13 converted: `9780439023481`, agrees with the scientific value. Loaded. |
| 2 | 18 Prisoner of Azkaban (books.csv) | `043965548X` | `9.78043965548e+12` | ISBN-10 already valid. ISBN-13 converted and agrees. Loaded. |
| 3 | 106 Bossypants (books.csv) | `` | `` | No ISBN. Loaded with a warning. |
| 4 | 622 (books.csv) | `446612707` | `9.78055381395e+12` | ISBN-10 `0446612707` valid; converted ISBN-13 `9780446612708` disagrees. ISBN-13 dropped, loaded with a warning. |
| 5 | 2778 Two-Way Street (books.csv) | `1416913184` | `9.78141691318e+12` | Fails ISBN-10 check; `9781416913184` is a valid ISBN-13 and agrees with the isbn13 column. ISBN-13 kept, ISBN-10 `1416913181` converted. Loaded with a warning. |
| 6 | 24 Goblet of Fire (batch2) | `0439139600` | `9780439139601` | Both valid and match. Same final values as the stored book. Skipped. |
| 7 | 132 Five People... (batch2) | `1401308589` | `9.78140130858e+12` | Valid, ISBN-13 `9781401308582` agrees. Ratings changed. Updated. |
| 8 | 10002 Salt and Ember (batch2) | `0-450-19827-8` | `9780450198274` | Hyphens removed: `0450198278`, matches ISBN-13. Loaded. |
| 9 | 10004 Winter Orchard (batch2) | `031200009x` | `9780312000097` | `x` → `X`: `031200009X`, matches ISBN-13. Loaded. |
| 10 | 10014 Atlas of Small Kindnesses (batch2) | `9781982147600` | `` | Valid ISBN-13 in the ISBN-10 column. ISBN-13 `9781982147600`, ISBN-10 `1982147601` converted. Loaded with a warning. |
| 11 | 10006 Notes from the Night Ferry (batch2) | `` | `9798351220413` | Valid 979 ISBN-13, no ISBN-10. Loaded. |
| 12 | 10008 The Glass Aviary (batch2) | `04390A3483` | `` | Illegal character: ISBN-10 dropped; no ISBN left. Loaded with warnings. |
| 13 | 10009 Borrowed Light (batch2) | `15287463097` | `` | Wrong length: dropped; no ISBN. Loaded with warnings. |
| 14 | 10011 Tides of Marrow Bay (batch2) | `1555550126` | `9781555550134` | Both valid, don't match. Rejected. |
| 15 | 10013 Paper Moons (batch2) | `1416524797` | `` | ISBN belongs to book 9 (Angels & Demons). Rejected. |
| 16 | 10001 Lantern Keeper's Daughter, 2nd copy (batch2) | `1528746309` | `9781528746304` | Same book_id and values as the row before it. Skipped. |
| 17 | 25 Deathly Hallows (batch2) | `` | `` | No ISBN in the new row; stored ISBNs kept; nothing else changed. Skipped, with a warning. |


## 9. Answers to Claude's questions

1. **Rule 1.4, two different valid ISBN-13s:** if the `isbn` column holds a valid ISBN-13 and the `isbn13` column holds a different valid ISBN-13, keep the `isbn13` column's value, drop the value from the `isbn` column, and give a warning. The ISBN-10 is converted from the kept ISBN-13 (rule 2.7).
2. **Rule 1.5, "agrees":** when the `isbn13` column is already a valid ISBN-13 as text, "agrees" means the two are identical.
3. **Warning count:** the run's warning count is the number of rows that have at least one warning, whatever happened to them (loaded, updated or skipped). Every such row is listed in the log.
4. **Row number:** the first row after the header is row 1.
5. **Updating a book:** when a book is updated, its stored original `isbn` and `isbn13` text is replaced with the new row's, except when rule 6.3 keeps the stored ISBNs (then the stored original text is kept too).
6. **Broken rows (empty `book_id`, wrong number of columns):** the row is rejected.
7. **A crash mid-run:** the whole run is undone (nothing from that run stays in books.db) and the run is still logged, marked as not finished.
8. **Rule 5.2 and updates:** rule 5.2 also applies when an existing book is updated. If the new row's ISBN belongs to a different book, the row is rejected and the stored book is left unchanged.
9. **Rule 6.4, what counts as changed:** compare the final values after all the rules (including rule 2.6). A book only counts as changed if a final value differs from the stored one.