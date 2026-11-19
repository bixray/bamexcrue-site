# Bamex Crue — PythonAnywhere free deployment

This Flask site stores inquiries in SQLite and includes a private dashboard. The free PythonAnywhere plan gives the site a `YOUR-PYTHONANYWHERE-USERNAME.pythonanywhere.com` address. It does **not** connect `bamexcrue.com`; custom domains require a paid PythonAnywhere plan.

The Beginner plan has limited daily CPU and restricted outbound internet. The site may take time to respond under those limits. SMTP email alerts may be blocked by outbound-network restrictions; inquiries still save to SQLite and can be reviewed in the dashboard.

## 1. Create the free web app

1. Sign up for a free [PythonAnywhere Beginner account](https://www.pythonanywhere.com/registration/register/beginner/).
2. Open the **Web** tab and add a web app using **Manual configuration** and Python 3.13 (or another version also selected for the virtual environment).
3. Open a **Bash console** from the **Consoles** tab.

## 2. Clone and install the app

Run these commands in the PythonAnywhere Bash console:

```bash
git clone https://github.com/bixray/bamexcrue-site.git ~/bamexcrue-site
python3.13 -m venv ~/.virtualenvs/bamexcrue
~/.virtualenvs/bamexcrue/bin/pip install -r ~/bamexcrue-site/requirements.txt
cp ~/bamexcrue-site/.env.example ~/bamexcrue-site/.env
chmod 600 ~/bamexcrue-site/.env
python3.13 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Copy the random value printed by the last command, open `~/bamexcrue-site/.env` in PythonAnywhere's **Files** tab, and replace the example values:

- `SECRET_KEY`: the random value you just generated.
- `ADMIN_PASSWORD`: a unique password of at least 16 characters.

Keep `.env` private. It is excluded from Git. Do not paste these values into chat or commit them.

## 3. Configure the web app

In the **Web** tab, set the virtualenv to:

```text
/home/YOUR-PYTHONANYWHERE-USERNAME/.virtualenvs/bamexcrue
```

Open the WSGI configuration file link on that page and replace its contents with:

```python
import os
import sys

project_home = os.path.expanduser("~/bamexcrue-site")
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from pythonanywhere_wsgi import application
```

Save the WSGI file, then click **Reload** in the Web tab. Replace `YOUR-PYTHONANYWHERE-USERNAME` above with the username shown in your PythonAnywhere account.

## 4. Check the site

Open `https://YOUR-PYTHONANYWHERE-USERNAME.pythonanywhere.com`, submit a test inquiry, and sign in at `/admin` using the admin password you set in `.env`. The database file is `~/bamexcrue-site/bamexcrue.db`; do not delete it. Make backups of it regularly.

Your GitHub username may differ from your PythonAnywhere username. Use the PythonAnywhere username for the website URL and virtualenv path.

## Email alerts

Email alerts are optional. PythonAnywhere free accounts restrict outbound internet, so SMTP delivery may not be available. Do not rely on email alerts unless you have tested them from the deployed site. The website's WhatsApp and email links remain available, and saved inquiries can be read in `/admin`.

## Privacy and terms

The privacy and terms pages are drafts based on the provided business name and Uganda. Have them reviewed for accuracy and local legal requirements before launch.
