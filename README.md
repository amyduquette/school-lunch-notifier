# School Lunch Notifier

A Python app that retrieves daily school lunch menus from Nutrislice and
automatically emails the next day's menu to parents.

This project is being built incrementally. The first milestone retrieves and
prints a menu locally. Email delivery and Render deployment come later.

## 1. Retrieve a menu locally

You need Python 3.11 or newer. This milestone uses only Python's standard library;
there are no packages to install.

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

The date is explicit for now. The scheduled version will select tomorrow using
Eastern Time.

### Missing menus and errors

- A school notice in `holiday_text` is shown instead of lunch choices, even if
  the response also contains choices.
- An empty menu prints an explanation. An empty response alone cannot tell us
  whether school is closed or the menu is unpublished.
- Network failures, HTTP errors, invalid JSON, unexpected response formats, and
  a response for the wrong date print an error to stderr and exit with status 1.
- A valid response, including a holiday or an empty menu, exits with status 0.

The script does not substitute another day's menu or use a cached menu.

## Next milestones

1. Add email delivery with credentials and the two recipients in environment
   variables, then send a test email.
2. Commit and push the working application to GitHub.
3. Optionally follow Render's [Flask quickstart](https://render.com/docs/deploy-flask)
   as a separate learning exercise for web services.
4. Deploy the notifier as a [Render cron job](https://render.com/docs/cronjobs),
   configure secrets, trigger a manual run, and inspect its logs.
5. Add the 6 PM Eastern, Sunday-through-Thursday schedule and test the time guard.

Render's cron documentation currently specifies UTC schedules, billing by active
runtime, and a $1 monthly minimum per cron job. A small job may stay near that
minimum, but this is not a free service or a fixed-price guarantee. Check the
[cron documentation](https://render.com/docs/cronjobs) before deployment.

For daylight saving time, the planned UTC schedule is `0 22,23 * * SUN-THU`.
The script will run its work only when the time in `America/New_York` is 6 PM,
so the extra daily invocation exits without sending. This avoids manually
changing the schedule when daylight saving time starts or ends. Scheduling is
not implemented in this milestone.

## Menu source

- [Central Elementary lunch menu](https://msad35.nutrislice.com/menu/central-elementary/lunch/)
- API URL pattern:
  `https://msad35.api.nutrislice.com/menu/api/digest/school/central-elementary/menu-type/lunch/date/{year}/{month}/{day}/`

## Secrets

Keep email credentials and recipient addresses in environment variables. Local
`.env` files are ignored by Git; the current script does not load them. It needs
no credentials to retrieve the public menu.
