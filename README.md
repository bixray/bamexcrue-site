# Bamex Crue

Flask application for the Bamex Crue website, inquiry form, SQLite database, and private inquiry dashboard.

## Deploy to Render

This folder is the deployable project. Do not publish the parent Documents folder: it contains unrelated files. The Render blueprint in `render.yaml` configures the app, persistent SQLite disk, health check, custom domain, and generated session key.

1. Create a **public** GitHub repository named `bamexcrue-site`, and upload only the files in this folder.
2. In Render, choose **New → Blueprint**, connect that repository, and review the Blueprint before applying it.
3. Render will display the price before provisioning the paid web service and persistent disk. Confirm it only if the recurring price is acceptable.
4. Enter a unique admin password of at least 16 characters for `ADMIN_PASSWORD` in Render's private environment settings. Never commit it or share it in chat.
5. After the service is created, open its custom-domain instructions. At your domain registrar, add the exact DNS records Render provides for `bamexcrue.com`. DNS changes must be made in the registrar account by its owner. Wait for Render to verify the domain and HTTPS certificate.
6. Open `https://bamexcrue.com`, test a request, then open `https://bamexcrue.com/admin` and sign in.

The inquiry database is stored on the Render persistent disk at `/var/data/bamexcrue.db`. Keep regular backups. Deploying a new version must not remove this disk.

## Email alerts (optional)

The contact form and dashboard work without email. To enable alerts to `kizyben47@gmail.com`, add these environment variables in Render's private environment settings. Use an SMTP app password or dedicated SMTP credential:

- `SMTP_HOST`
- `SMTP_PORT` (usually `587`)
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM` (an address approved by your email provider)

Never put SMTP credentials in this repository or in the HTML. Test email delivery with a real submission after adding them.

## Local development on Windows

```powershell
$python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
& $python -m pip install -r requirements.txt
$env:SECRET_KEY = (& $python -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
$env:ADMIN_PASSWORD = "REPLACE_WITH_YOUR_OWN_LONG_PRIVATE_PASSWORD"
& $python server.py
```

Open <http://127.0.0.1:8000> for the site and <http://127.0.0.1:8000/admin> for the dashboard.

## Legal pages

The privacy and terms pages are drafts based on the provided business name and Uganda. Have them reviewed for accuracy and local legal requirements before launch.

## Hosting note

GitHub Pages is static-only and cannot run this backend. The public GitHub repository contains the site's source; Render runs the Python app and serves the public website.
