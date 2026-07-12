# PDF Text Extractor

Connects to your **Box Online** account via the Box API, finds password-protected PDF files, decrypts them, and exports the extracted content to **Word**, **CSV**, and **JSON** formats.

---

## Project Structure

```
PDF Extractor/
├── pdf_text_extractor.py   ← Main application
├── config.json             ← Configuration (Box API credentials, PDF password, settings)
├── requirements.txt        ← Python dependencies
├── extractor.log           ← Activity log (created on first run)
├── Word Extracts/          ← Exported .docx files
├── CSV Extracts/           ← Exported .csv files
└── JSON File Extracts/     ← Exported .json files
```

---

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create a Box App & Get Your Credentials

1. Go to [https://app.box.com/developers/console](https://app.box.com/developers/console)
2. Click **Create New App** → choose **Custom App** → **User Authentication (OAuth 2.0)**
3. Once created, go to the app's **Configuration** tab
4. Scroll to **Developer Token** → click **Generate Developer Token**
5. Copy the token — it is valid for **60 minutes**

> **For production / long-running use:** Set up a **JWT** or **Client Credentials Grant (CCG)** app in the Box Developer Console and update the `get_box_client()` function in `pdf_text_extractor.py` accordingly.

### 3. Find Your Box Folder ID

- Open [https://app.box.com](https://app.box.com) in your browser
- Navigate to the folder that contains your PDFs
- The **numeric ID** is in the URL: `https://app.box.com/folder/`**`123456789`**
- Use `"0"` to scan your entire root Box folder

### 4. Edit `config.json`

Open [`config.json`](config.json) and fill in the required values:

```json
{
  "pdf_password": "your_pdf_password",
  "box": {
    "client_id":     "your_box_client_id",
    "client_secret": "your_box_client_secret",
    "access_token":  "your_developer_token",
    "folder_id":     "123456789"
  },
  "settings": {
    "search_subfolders": true,
    "overwrite_existing_exports": true
  }
}
```

| Key | Description |
|-----|-------------|
| `pdf_password` | Password to decrypt your PDF files |
| `box.client_id` | Your Box App's Client ID |
| `box.client_secret` | Your Box App's Client Secret |
| `box.access_token` | Developer Token (or OAuth2 access token) |
| `box.folder_id` | Numeric ID of the Box folder to scan (`"0"` = root) |

> **Note:** `pdf_password` is intended to be replaced by a Password Manager integration in a future version for improved security.

### 5. Run the Extractor
```bash
python pdf_text_extractor.py
```

---

## What It Does — Step by Step

1. **Loads** `config.json` for Box credentials and the PDF password
2. **Connects** to Box Online via the Box SDK using your access token
3. **Scans** the configured Box folder (and subfolders, if enabled) for `.pdf` files
4. **Downloads** each PDF file into memory (nothing is saved to disk from Box)
5. **Decrypts** each password-protected PDF using the configured password
6. **Extracts** all raw text, page by page
7. **Parses** key-value fields from the text (e.g. `Name: John`, `Last Name: Doe`)
8. **Exports** three output files per PDF:

| Output | Location | Contents |
|--------|----------|----------|
| `.docx` | `Word Extracts/` | Full raw text, one section per page |
| `.csv`  | `CSV Extracts/`  | One column per detected field (Name, Last Name, etc.) |
| `.json` | `JSON File Extracts/` | Structured JSON with fields + full page text |

---

## CSV Output Format

Fields detected in the PDF (e.g. `Name`, `Last Name`, `Date of Birth`) become **column headers** in row 1, with their values in row 2. This makes it easy to open directly in Excel.

**Example:**

| Name | Last Name | Date of Birth |
|------|-----------|---------------|
| John | Doe       | 01/01/1990    |

---

## Settings Reference (`config.json`)

| Setting | Default | Description |
|---------|---------|-------------|
| `search_subfolders` | `true` | Scan subdirectories inside the Box folder |
| `overwrite_existing_exports` | `true` | Overwrite previously generated exports |
| `log_activity` | `true` | Write activity log to `extractor.log` |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `PyMuPDF` | Open, decrypt, and extract text from PDF files |
| `python-docx` | Generate Word `.docx` export files |
| `openpyxl` | Excel/CSV workbook support |
| `boxsdk` | Connect to Box Online and download files via the Box API |

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Box access_token is not set` | Paste your Developer Token into `config.json → box.access_token` |
| `Could not list Box folder` | Check that your `folder_id` is correct and your token has not expired (Developer Tokens expire after 60 min) |
| `Incorrect password` | Update `pdf_password` in `config.json` |
| `No PDF files found` | Confirm the `folder_id` points to the correct Box folder and the folder contains `.pdf` files |
| `config.json not found` | Make sure `config.json` is in the same folder as the script |
