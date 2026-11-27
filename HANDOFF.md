# Find-IT Handoff — Account management and user profile

> Newest work is first. The earlier handoff for the **item category and location** feature is kept unchanged at the bottom of this file.

## 1. Feature completed

### Module 1 — Registration, login, and role assignment

- **Student registration** (`/signup/`) asks for first name, last name, Student ID, email address, password, and confirm password.
  - Every field is required and checked.
  - The Student ID must use the existing `YYYY-NNNN` format. This checks the **format only**. It does **not** verify real enrollment, and the page says so.
  - Duplicate Student IDs and duplicate email addresses are refused. The email check ignores letter case.
  - Passwords go through Django's password-strength validators, and both password boxes must match.
  - The **Student** role is assigned in code. Any role, `is_staff`, or `is_superuser` value added to the form is ignored.
  - Clear error messages appear beside each field, and a success message appears after sign-up.
- **Login** (`/login/`)
  - Students sign in with their Student ID. Staff and administrators sign in with their assigned username.
  - Each password box has a **Show/Hide** button, including the sign-in pop-up.
  - A wrong password and a suspended account both show the same safe error, so the page doesn't reveal which accounts exist.
  - Sign-in uses Django's session login, which rotates the session key. A `?next=` page is honoured only if it is on the same site.
  - After sign-in, students go to **Browse** and staff and administrators go to the **Staff workspace**, unless a safe `next` page was requested.
- **Roles.** There are still exactly three roles: Student, Staff, and Administrator. No Teacher role was added.
  - Students register themselves.
  - Staff accounts are created **only** by an administrator.
  - No page lets anyone change a role.
- **Admin account management** (`/staff/accounts/`, administrators only)
  - Create staff accounts with first and last name, username, optional email, and a temporary password with confirmation. The new account always gets the Staff role.
  - See the current staff list.
  - **Activate or Suspend** a staff account. Suspending ends that person's open sessions immediately.
  - See an **All accounts and roles** table, which can be filtered by role.
  - Every creation, suspension, and activation is written to the existing staff audit log.
  - The activate/suspend action works only on Staff accounts. Students, administrators, and the admin's own account are refused.
- **Backend permission checks** are on every new page and action.
  - Signed-out users are sent to log in.
  - Students get *403 Forbidden* on staff and admin pages, and staff get it on admin pages.
  - Activate/suspend accepts POST only.
  - All forms are protected with CSRF.

### Module 2 — View and edit user profile

- **My profile** (`/profile/`) shows the profile picture (or an initial), full name, Student ID or username, email, contact number, role, registration date, and account status.
- **Edit profile** (`/profile/edit/`)
  - Users can update first name, last name, email, contact number, and profile picture, and can remove the current picture.
  - **Save changes** and **Cancel** buttons are included.
  - Validation:
    - First name and email are required.
    - Duplicate emails are refused.
    - Contact number allows digits, spaces, dashes, and a leading `+`, with 7–15 digits.
    - Pictures must be real JPG, PNG, or WebP images up to **2 MB**. Pillow checks the file contents, not just the name.
  - When a picture is replaced or removed, the old file is deleted.
  - Changes appear immediately on the profile page and in the header.
  - Student ID, username, role, and status appear in a locked box and **cannot** be edited. The edit page has no user ID in its address, so each user can only ever edit their own profile.
- **Change password** (`/profile/password/`) uses Django's own `PasswordChangeForm`.
  - It asks for the current password, the new password, and the new password again.
  - The new password goes through the strength validators.
  - This browser stays signed in, and other devices are signed out.
- **Navigation**
  - A **My profile** link was added to the main navigation.
  - A **profile dropdown** sits at the upper right: avatar and name, then My profile, Edit profile, Change password, Staff accounts (administrators only), and Log out.
  - All new pages reuse the existing Find-IT colours, cards, buttons, and fonts, and work on phone screens.

## 2. Starting version

- Repository: `jblloydg/1`, branch `main`
- Starting commit: **`c54da44`**, "Add item category and location filters to Find-IT". That commit was itself built on the original **`9f0b2ad`**.

## 3. Files changed

All paths are inside `Find-IT/`. Root files (`README.md`, `LICENSE`, `Find-IT-local-app.zip`) are still unchanged.

Changed:

| File | Change |
| --- | --- |
| `core/models.py` | `Profile.contact_number` and `Profile.photo` |
| `core/validators.py` | `validate_profile_photo`: JPG, PNG, or WebP, up to 2 MB |
| `core/forms.py` | Login form messages and toggles; `SignupForm` with email and duplicate checks; `StaffAccountForm` with email and password confirmation; new `ProfileForm`; new `FindItPasswordChangeForm` |
| `core/views.py` | Role-based login redirect and messages; signup messages; `my_profile`, `edit_profile`, `change_password`; `staff_accounts` list and role filter; new `staff_account_status` |
| `core/urls.py` | `/profile/`, `/profile/edit/`, `/profile/password/`, `/staff/accounts/<id>/status/` |
| `core/context_processors.py` | Adds `current_role_label` for the dropdown |
| `core/admin.py` | Django admin user list shows email and Find-IT role, plus a role filter; the profile inline shows contact number and picture |
| `core/management/commands/seed_demo.py` | Demo accounts get first and last names and fictional `@example.com` emails |
| `core/tests.py` | 48 new tests (56 in total) |
| `templates/core/base.html` | My profile link, profile dropdown, password toggle in the sign-in pop-up |
| `templates/core/login.html`, `signup.html`, `staff_accounts.html` | Updated forms and pages |
| `static/css/app.css` | New styles added at the end; also a small fix so the category and location tags from the earlier feature are not stretched |
| `static/js/app.js` | Show/Hide password buttons and dropdown closing, added at the end |

Added:

| File | Purpose |
| --- | --- |
| `core/migrations/0003_profile_contact_photo.py` | Adds the two new Profile fields |
| `templates/core/profile.html` | My profile |
| `templates/core/profile_edit.html` | Edit profile |
| `templates/core/change_password.html` | Change password |
| `templates/core/includes/avatar.html` | Small reusable picture-or-initial block |

Not touched: listings, claims, comments, messaging and chat, notifications, reports, timers, and their templates.

## 4. Database fields and migrations

Migration **`0003_profile_contact_photo`**, table `core_profile`:

| Field | Type | Rules |
| --- | --- | --- |
| `contact_number` | `CharField(max_length=20)` | Optional; blank by default |
| `photo` | `ImageField(upload_to="profile-photos/%Y/%m/")` | Optional; nullable; JPG, PNG, or WebP up to 2 MB |

- Both fields are optional, so **existing user records are kept as they are**.
- Email, first name, last name, registration date (`date_joined`), and status (`is_active`) already exist on Django's built-in user table, so no new columns were needed for them.
- The migration uses only standard Django fields and works on SQLite now and on PostgreSQL later.

## 5. Set up and run on Windows PowerShell

You need Python 3.12 or later and Git.

```powershell
# 1. Get the newest code
git clone https://github.com/jblloydg/1.git findit-repo
cd findit-repo\Find-IT
#    (If you already have the clone: cd into findit-repo, run "git pull", then cd Find-IT)

# 2. Create and activate a virtual environment (skip if .venv already exists)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install packages
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Update the database and create the fictional demo accounts
python manage.py migrate
python manage.py seed_demo

# 5. Start the website and the local timer runner
.\start_findit.ps1
```

If PowerShell blocks a script, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_findit.ps1
```

Open **http://127.0.0.1:8000/** and stop the site with **Ctrl+C**. Uploaded profile pictures are saved in the local `media\` folder, which Git ignores.

To run the automated tests:

```powershell
python manage.py test core
```

## 6. See the feature working

These are the public fictional demo logins from the original README.

| Role | Sign-in name | Password |
| --- | --- | --- |
| Student | 2026-0001 | DemoFindIt!2026 |
| Staff | security.demo | DemoStaff!2026 |
| Administrator | findit-admin | DemoAdmin!2026 |

1. **Register.** Open **/signup/**. Try the Student ID `20260003` and see the format error. Try `2026-0001` and see the duplicate-ID error. Try the email `alex.finder@example.com` and see the duplicate-email error. Then sign up with `2026-0003`, a new email, and a strong password. You are signed in as a **Student**.
2. **Show/Hide.** On **/login/**, type a password and click **Show**, then **Hide**.
3. **Student login.** Log out, then sign in as `2026-0001`. You land on **Browse**.
4. **Profile dropdown.** Click your name at the upper right. Choose **My profile** to see every account detail.
5. **Edit profile.** Click **Edit profile**. Change your last name, add a contact number such as `0917 123 4567`, and upload a JPG or PNG. Click **Save changes**. The new details and picture appear right away, including in the header. Note that Student ID, role, and status are locked.
6. **Bad inputs.** Edit again with the email `jamie.claimant@example.com`, which is already used. You see an error, and nothing is saved.
7. **Change password.** Open **Change password**. Enter a wrong current password and see the error. Then change it properly and see the success message.
8. **Staff login.** Log out and sign in as `security.demo`. You land on the **Staff workspace**. Visit **/staff/accounts/** and you get *Forbidden*.
9. **Admin.** Sign in as `findit-admin`, then open **Staff → Staff accounts**, or the dropdown's **Staff accounts** link.
   - Create a staff account.
   - Click **Suspend** on *Campus Staff*, then try signing in as `security.demo` in a private window. It is refused.
   - Click **Activate** to restore it.
   - Use the **All roles** filter on the accounts table.

## 7. Unfinished items and setup notes

- **The email rule is enforced by the forms, not the database.** Signup, profile edit, and staff creation all refuse duplicate emails. Django's built-in user table doesn't make email unique, though, and changing that would need a custom user model and a risky migration. Accounts created another way, such as **Django admin** or `createsuperuser`, could still share an email.
- **Existing demo accounts keep their old names.** If you already had a local database, `seed_demo` won't change existing accounts. Alex's name stays as first name "Alex Finder" with no last name, and there is no email. Fix it on **Edit profile**, or delete your local `db.sqlite3` and run the setup steps again.
- **Student accounts are not suspended from the account page.** As before, an administrator restricts a student through a safety report (**Staff → Reports**). The account page suspends and activates Staff accounts only, as the instructions asked.
- **No password reset by email.** No email sending has been configured yet. A student who forgets a password needs an administrator to reset it in Django admin.
- **Student ID is a format check only.** It does not prove enrollment, and no verification is claimed.
- **Profile pictures are stored locally** in `media/`. For online hosting, configure durable media storage as the original README says.
- **Testing:** done with Python 3.13 and Django 5.2.19 on Linux. `manage.py check` found no issues, and **56 of 56** tests passed. The login, sign-up, profile, edit, and staff-accounts pages were also checked in a real browser, on desktop and phone sizes. It was not run on a Windows machine.
- **Nothing private is included.** No `db.sqlite3`, no `media/`, no `.env`, no secret keys, and no real student data. The only passwords are the public fictional demo ones, and the tests use throwaway test passwords.

---

## Earlier handoff — Item category and location filter (commit c54da44)

### 1. Feature completed

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

### 2. Starting version

- Repository: `jblloydg/1`, branch `main`
- Starting commit: **`9f0b2ad`**, "Initial commit: FindIT campus lost and found system"
- Source: the app inside `Find-IT-local-app.zip` from that commit

### 3. Files changed

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

### 4. Database fields and migrations

Table `core_itempost`:

| Field | Type | Rules |
| --- | --- | --- |
| `category` | `CharField(max_length=16)`, indexed | Required; one of the choices above; default `OTHER` |
| `location` | `CharField(max_length=120)` | Optional; blank by default |

- `0001_initial.py` was not in the zip. The original README asked you to generate it with `makemigrations`. It is now included and committed, as the README recommended, so you no longer need to run `makemigrations`. If you do run it, it should say "No changes detected".
- `0002_item_category_location.py` adds only the two columns above. It uses only standard Django fields, so it works on SQLite now and on PostgreSQL later without changes.

### 5. Set up and run on Windows PowerShell

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

### 6. See the feature working

1. Sign in with the fictional demo account **2026-0001** and the password **DemoFindIt!2026**. This is the public demo login from the original README.
2. On **Browse items**, each card now has a teal category tag and a 📍 location tag. The bottle shows *Bottle or container* and *Library 2nd floor*. The umbrella shows *Umbrella* and *Canteen*.
3. In the **All categories** dropdown, choose **Umbrella** and click **Search**. Only the umbrella remains.
4. Click **Clear all filters**. Type `library` in the **Any location** box and click **Search**. Only the bottle remains.
5. Type `canteen` in the main search box with no other filters and click **Search**. The umbrella appears, because the keyword search now also checks location.
6. Click **＋ Create post**. Choose **Lost**, then category **Phone or electronics**, and enter a title, a description and the location `Gym`. Publish it. The detail page shows both tags.
7. On that detail page, click the category tag. You are taken back to the browse page filtered to *Phone or electronics*.

### 7. Unfinished items and setup notes

- **The category list is fixed in code** (`ItemPost.Category` in `core/models.py`). Administrators cannot add categories from the website yet. Adding one means editing that list and creating a new migration.
- **Location is free text**, not a list of Davao Oriental State University buildings. People may spell the same place differently, for example "Lib" and "Library". A fixed list of campus areas could be added later once the building names are confirmed.
- **The project now exists in two places.** `Find-IT-local-app.zip` still holds the original version, because existing files were not to be changed. The `Find-IT/` folder is the current, working version. Use the folder.
- **If you already ran the old version locally:** you can keep your existing `db.sqlite3` by copying it into the new `Find-IT/` folder and running `python manage.py migrate`. That applies only `0002` and keeps your data. Do not copy your old self-generated `core/migrations` folder over the committed one.
- **Testing:** this was tested with Python 3.13 and Django 5.2.19 on Linux (8 automated tests plus page checks). It was not run on a Windows machine. The PowerShell steps are the same ones as the original README, minus `makemigrations`.
- **Nothing private is included.** No `db.sqlite3`, no uploaded media, no `.env`, no secret keys, and no real student data. The only passwords mentioned are the public fictional demo passwords from the original README. `Find-IT/.gitignore` keeps `db.sqlite3`, `.env` and `media/` out of Git.
