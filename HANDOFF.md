# Find-IT Handoff — Item category and location filter

## 1. Feature completed

Every lost or found post now has:

- **Category** (required, from a fixed list): ID or card, Phone or electronics, Bag or wallet, Keys, Books or school supplies, Clothing or accessories, Bottle or container, Umbrella, Other.
- **Campus location** (optional, short free text): a broad area where the item was lost or found, such as "Library 2nd floor" or "Canteen".

Where the feature shows up:

- **Create post / Edit post** has a Category dropdown and a Campus location box.
- **Browse page (/home/)** has two new filters: **All categories** and **Any location**. They combine with the existing keyword, type and status filters. The keyword search now also matches the location. A **Clear all filters** link appears whenever a filter is active.
- **Post cards and the post detail page** show a category tag and a 📍 location tag. On the detail page, the category tag links to the browse page filtered to that category.
- **Django admin (/django-admin/)** lists category and location, filters by category, and searches by location.
- **Demo data (seed_demo)** gives the demo bottle the category *Bottle or container* at *Library 2nd floor*, and the demo umbrella the category *Umbrella* at the *Canteen*.

Posts that existed before this change automatically get the category **Other** and a blank location, so no data is lost.

## 2. Starting version

- Repository: `jblloydg/1`, branch `main`
- Starting commit: **`9f0b2ad`**, "Initial commit: FindIT campus lost and found system"
- Source: the app inside `Find-IT-local-app.zip` from that commit

## 3. Files changed

The original files at the repository root (`README.md`, `LICENSE`, `Find-IT-local-app.zip`) are **unchanged**. The full working project, with the new feature, is now unpacked in the new **`Find-IT/`** folder. Everything in that folder is the same as the zip except the files below.

Changed:

| File | Change |
| --- | --- |
| `Find-IT/core/models.py` | Added the `ItemPost.Category` choices and the `category` and `location` fields |
| `Find-IT/core/forms.py` | Added `category` and `location` to the post form |
| `Find-IT/core/views.py` | Added the category and location filters to the `home` view; keyword search also matches location |
| `Find-IT/core/admin.py` | Category and location in the admin list, filter and search |
| `Find-IT/core/management/commands/seed_demo.py` | Demo posts get a category and location |
| `Find-IT/templates/core/home.html` | New filter controls, Clear-filters link, tags on cards |
| `Find-IT/templates/core/post_form.html` | Category and location inputs |
| `Find-IT/templates/core/post_detail.html` | Category and location tags |
| `Find-IT/static/css/app.css` | Styles for the tags and filter row, added at the end of the file |

Added:

| File | Purpose |
| --- | --- |
| `Find-IT/core/migrations/__init__.py` | Migrations package |
| `Find-IT/core/migrations/0001_initial.py` | Baseline migration of the original Find-IT models, unchanged from commit 9f0b2ad |
| `Find-IT/core/migrations/0002_item_category_location.py` | Adds the two new fields |
| `Find-IT/core/tests.py` | 8 automated tests for this feature |
| `HANDOFF.md` | This file |

## 4. Database fields and migrations

Table `core_itempost`:

| Field | Type | Rules |
| --- | --- | --- |
| `category` | `CharField(max_length=16)`, indexed | Required; one of the choices above; default `OTHER` |
| `location` | `CharField(max_length=120)` | Optional; blank by default |

- `0001_initial.py` was not in the zip. The original README asked you to generate it with `makemigrations`. It is now included and committed, as the README recommended, so you no longer need to run `makemigrations`. If you do run it, it should say "No changes detected".
- `0002_item_category_location.py` adds only the two columns above. It uses only standard Django fields, so it works on SQLite now and on PostgreSQL later without changes.

## 5. Set up and run on Windows PowerShell

You need Python 3.12 or later and Git.

```powershell
# 1. Get the code (or run "git pull" inside an existing clone)
git clone https://github.com/jblloydg/1.git findit-repo
cd findit-repo\Find-IT

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install packages
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Create the local database and the fictional demo accounts
python manage.py migrate
python manage.py seed_demo

# 5. Start the website and the local timer runner
.\start_findit.ps1
```

If PowerShell blocks a script, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_findit.ps1
```

Open **http://127.0.0.1:8000/** and stop the site with **Ctrl+C**.

To run the automated tests (optional):

```powershell
python manage.py test core
```

## 6. See the feature working

1. Sign in with the fictional demo account **2026-0001** and the password **DemoFindIt!2026**. This is the public demo login from the original README.
2. On **Browse items**, each card now has a teal category tag and a 📍 location tag. The bottle shows *Bottle or container* and *Library 2nd floor*. The umbrella shows *Umbrella* and *Canteen*.
3. In the **All categories** dropdown, choose **Umbrella** and click **Search**. Only the umbrella remains.
4. Click **Clear all filters**. Type `library` in the **Any location** box and click **Search**. Only the bottle remains.
5. Type `canteen` in the main search box with no other filters and click **Search**. The umbrella appears, because the keyword search now also checks location.
6. Click **＋ Create post**. Choose **Lost**, then category **Phone or electronics**, and enter a title, a description and the location `Gym`. Publish it. The detail page shows both tags.
7. On that detail page, click the category tag. You are taken back to the browse page filtered to *Phone or electronics*.

## 7. Unfinished items and setup notes

- **The category list is fixed in code** (`ItemPost.Category` in `core/models.py`). Administrators cannot add categories from the website yet. Adding one means editing that list and creating a new migration.
- **Location is free text**, not a list of Davao Oriental State University buildings. People may spell the same place differently, for example "Lib" and "Library". A fixed list of campus areas could be added later once the building names are confirmed.
- **The project now exists in two places.** `Find-IT-local-app.zip` still holds the original version, because existing files were not to be changed. The `Find-IT/` folder is the current, working version. Use the folder.
- **If you already ran the old version locally:** you can keep your existing `db.sqlite3` by copying it into the new `Find-IT/` folder and running `python manage.py migrate`. That applies only `0002` and keeps your data. Do not copy your old self-generated `core/migrations` folder over the committed one.
- **Testing:** this was tested with Python 3.13 and Django 5.2.19 on Linux (8 automated tests plus page checks). It was not run on a Windows machine. The PowerShell steps are the same ones as the original README, minus `makemigrations`.
- **Nothing private is included.** No `db.sqlite3`, no uploaded media, no `.env`, no secret keys, and no real student data. The only passwords mentioned are the public fictional demo passwords from the original README. `Find-IT/.gitignore` keeps `db.sqlite3`, `.env` and `media/` out of Git.
