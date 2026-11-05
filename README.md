# Module 3 Assignment

This is my Module 3 assignment for MSAI-5523 (Language of Computing).

## How to run ingest.py

These steps are for this Windows computer, using PowerShell. `ingest.py` creates `books.db` and `ingestion-log.json` in the same folder as the script.

1. Open PowerShell: press the **Windows key**, type `PowerShell`, and press **Enter**.

2. Go to the assignment folder:

   ```powershell
   cd $HOME\workspace\language-of-computation\week3-assignment
   ```

3. Check that Python works (it should print `Python 3.13.17` or similar):

   ```powershell
   py --version
   ```

4. Load the first delivery:

   ```powershell
   py ingest.py books.csv
   ```

5. Load the first delivery again (nothing new should be loaded; every row should be skipped):

   ```powershell
   py ingest.py books.csv
   ```

6. Load the second delivery:

   ```powershell
   py ingest.py books-batch2.csv
   ```

Each run prints how many rows were read, loaded, updated, skipped, rejected, and had warnings, and adds an entry to `ingestion-log.json`.

### Starting over

To start from an empty database and an empty log, delete both files, then repeat steps 4–6:

```powershell
Remove-Item books.db, ingestion-log.json
```

## How to open report.html

1. Open the assignment folder in File Explorer (you can type `explorer .` in the same PowerShell window).
2. Double-click `report.html`. It opens in your web browser; no server is needed.
3. Click **Open ingestion-log.json** and choose `ingestion-log.json` from the assignment folder.
4. The runs appear newest first, each with its counts, the rejected rows, the rows with warnings, and the skipped rows.
