# School Lunch Notifier

A Python app that retrieves daily school lunch menus from Nutrislice and
automatically emails the next day's menu to parents.

This project is being built incrementally. You can retrieve and print a menu
locally, view it through a Flask web app, or email it through Gmail using a
manually triggered GitHub Actions workflow. Automatic scheduling is not enabled yet.

## 1. Retrieve a menu locally

You need Python 3.11. The command-line script uses only Python's standard library;
there are no packages to install to run it.

From the repository directory, run:

```powershell
python lunch_menu.py --date 2026-11-18
```

The script constructs the Nutrislice API URL from the date, retrieves its JSON
with a 20-second timeout, and prints the lunch choices:

```text
Central Elementary lunch
Wednesday, November 18, 2026

- Classic Cheese Pizza
- Traditional Pepperoni Pizza
- PB&J and Cheese Fun Lunch
- Bento Box: Soft Pretzel, Cheddar & Fresh Grapes
```

Choose any date with `--date YYYY-MM-DD`. For example, to inspect the menu for
Thursday, November 19:

```powershell
python lunch_menu.py --date 2026-11-19
```

The command-line script takes an explicit date. The web app defaults to tomorrow
using Eastern Time.

### Missing menus and errors

- A school notice in `holiday_text` is shown instead of lunch choices, even if
  the response also contains choices.
- An empty menu prints an explanation. An empty response alone cannot tell us
  whether school is closed or the menu is unpublished.
- Network failures, HTTP errors, invalid JSON, unexpected response formats, and
  a response for the wrong date print an error to stderr and exit with status 1.
- A valid response, including a holiday or an empty menu, exits with status 0.

The script does not substitute another day's menu or use a cached menu.

## 2. Run the web app locally

From the repository directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app run
```

Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/) in your browser. The page
shows tomorrow's menu as plain text, reusing the command-line script's fetching
and formatting functions. Tomorrow means the next calendar date in
`America/New_York`, including weekends and holidays; an unavailable menu is
shown as unavailable instead of substituting a different day.

To inspect a specific date, open
[http://127.0.0.1:5000/?date=2026-11-19](http://127.0.0.1:5000/?date=2026-11-19).
Invalid dates return HTTP 400. API errors return HTTP 502 with a friendly
message, while the error details go to the app's logs. Valid holiday and empty
menu responses return HTTP 200 with the same explanations as the script.

The dependencies are Flask for HTTP requests, Gunicorn for serving the app on
Render, and `tzdata` so Eastern Time works on Windows as well as Linux.
Use Flask's development server locally on Windows; Gunicorn runs on Render's
Linux hosts.

## 3. Deploy the web app on Render

Follow [Your First Render Deploy](https://render.com/docs/your-first-deploy)
and the [Flask quickstart](https://render.com/docs/deploy-flask). Commit and push
the web app files to GitHub before creating the service.

In the Render service creation form, use:

| Setting | Value |
| --- | --- |
| Service type | Web Service |
| Repository | `school-lunch-notifier` |
| Branch | `main` |
| Root Directory | Leave blank |
| Language | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app --bind 0.0.0.0:$PORT` |
| Compute | Free |
| Health Check Path (under Advanced) | `/health` |

The build command installs dependencies. The start command launches Gunicorn;
`app:app` refers to the Flask object named `app` inside `app.py`. The bind option
listens on all interfaces at Render's assigned port, following its
[port-binding guidance](https://render.com/docs/web-services#port-binding).
Enter this command in Render, where `$PORT` is expanded by its Linux shell.

The tracked `.python-version` file selects Python 3.11 on Render, matching the
local Python version. Render uses the latest available 3.11 patch release.
See [Setting Your Python Version](https://render.com/docs/python-version).
The menu web page needs no environment variables or secrets. The separate email
command uses the environment variables described below.

Click Deploy, then watch the build and startup output on the service's Deploys
page. Once it is Live, open its `onrender.com` URL. You can append
`?date=2026-11-19` to check a known menu, or `/health` to check that the app is
running without relying on Nutrislice. The health endpoint checks the web app,
not whether a menu has been published. Menu retrieval failures are logged by
Flask and can be inspected in Render's service logs.

Free web services sleep after 15 minutes without inbound traffic and wake on
the next request. That is suitable for this learning exercise; the web app does
not run a daily email scheduler. See
[Free instance limitations](https://render.com/docs/free).

## 4. Send the first test email from GitHub

Render hosts the menu website. GitHub Actions runs the email command using
your existing Gmail account. This avoids creating a separate email-service
account and works around the SMTP ports blocked on Render Free. Visiting the
website does not send email, and the workflow runs only when you start it
manually. The nightly schedule comes after confirming the first test.

### Add three GitHub secrets

Create a [Google app password](https://support.google.com/accounts/answer/185833)
named **School Lunch Notifier** if you have not already. App passwords require
2-Step Verification and an eligible Google account.

In the GitHub repository, open **Settings > Secrets and variables > Actions**.
Click **New repository secret** for each entry below:

| Secret name | Value |
| --- | --- |
| `GMAIL_ADDRESS` | The Gmail address that created the app password |
| `GMAIL_APP_PASSWORD` | Your generated app password; spaces are accepted |
| `EMAIL_RECIPIENTS` | Your own email address for the first test |

GitHub passes these secrets to the send step as environment variables. See
[Using secrets in GitHub Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).
The tracked `.env.example` contains only the variable names. Local `.env` files
are ignored by Git, but the scripts do not automatically load them.

### Push and run the workflow

Commit and push the email code and workflow to `main`:

```powershell
git add notify.py tests/test_notify.py .env.example .github/workflows/test-email.yml README.md
git commit -m "Add Gmail email delivery and manual test workflow"
git push
```

Then, in GitHub:

1. Open **Actions > Send test email**.
2. Click **Run workflow** and select `main`.
3. Enter `2026-11-19` as the menu date to test a known menu, or leave it blank
   to use tomorrow in Eastern Time.
4. Click **Run workflow** and open the run to view its logs.

The workflow installs dependencies, runs the automated checks, then sends one
email with `[TEST]` in its subject. Its only trigger is `workflow_dispatch`,
so pushing a commit does not send email. See
[Manually running a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

Look for a message saying Gmail accepted the menu, then check your inbox and
Sent folder. Server acceptance alone does not confirm inbox delivery. After
the first test succeeds, update the `EMAIL_RECIPIENTS` secret to both parents'
addresses, separated by a comma. No code change is needed for that update.

### Preview locally

No credentials are needed for a preview:

```powershell
.\.venv\Scripts\python.exe notify.py --date 2026-11-19 --test
```

`notify.py` only sends when passed `--send`. `--test` adds `[TEST]` to the
subject; it does not bypass any menu checks or change the recipients. Without
`--date`, the command uses tomorrow's calendar date in `America/New_York`.
The Gmail connection uses SMTP over verified TLS on port 465, with the same
Gmail address for sign-in and the email sender.

### Skips and errors

- Weekend targets, school notices, and empty or blank menus are skipped, even
  with `--test --send`. A skip exits successfully without contacting Gmail.
- Menu API errors, invalid responses, missing configuration, and email errors
  exit with status 1. A response for another date is never emailed.
- Credentials and recipient addresses are not printed in the status messages.
- The command sends once and does not retry an uncertain send. If the connection
  times out or fails during sending, check Gmail's Sent folder before retrying
  to avoid duplicate messages. If only some recipients are accepted, the run
  reports the partial failure instead of reporting full success. Repeating a
  successful command sends another email; persistent deduplication is not
  implemented in this manual milestone.

Run the automated email checks with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

These checks mock the provider and do not send real email. A real test still
requires your account configuration and a confirmed inbox result.

## Next milestones

1. Run **Send test email** after adding the three secrets and confirm inbox delivery.
2. Configure a Sunday-through-Thursday, 6 PM Eastern schedule. GitHub Actions is
   an option that can avoid a hosting charge, within its free usage allowances.
   See [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
   and [scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
3. Test daylight saving time, holidays, and API failures before enabling
   unattended emails.

Render's managed cron jobs are an alternative, with a $1 monthly minimum per
job. They use UTC schedules, so that option would need an Eastern Time guard.
See [Render cron jobs](https://render.com/docs/cronjobs). Scheduling remains a
separate milestone from the free web deployment.

## Menu source

- [Central Elementary lunch menu](https://msad35.nutrislice.com/menu/central-elementary/lunch/)
- API URL pattern:
  `https://msad35.api.nutrislice.com/menu/api/digest/school/central-elementary/menu-type/lunch/date/{year}/{month}/{day}/`

## Secrets

Keep email credentials and recipient addresses in environment variables. Local
`.env` files are ignored by Git; the current script does not load them. It needs
no credentials to retrieve the public menu.
