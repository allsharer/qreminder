# qremind

A lightweight command-line reminder app for Linux desktops. Reminders are stored in a flat file and surfaced as desktop notifications (via `zenity` or `notify-send`) on a configurable schedule, driven by a systemd user timer or a background daemon.

## Requirements

- Python 3.6+
- `zenity` (default) or `notify-send` for notifications

## Installation

```sh
git clone git@github.com:allsharer/qreminder.git ~/.local/bin/qreminder
ln -s ~/.local/bin/qreminder/qremind ~/bin/qremind
```

Then install a systemd user timer to check for due reminders automatically:

```sh
qremind --install
```

## Usage

```
qremind --add                            Add a new reminder interactively
qremind --list                           List all reminders with status
qremind --month                          List pending reminders for the current calendar month
qremind --web                            Start the web UI at http://localhost:8765
qremind --web 9000                       Start the web UI on a custom port
qremind --edit                           Select a reminder to edit interactively
qremind --edit N                         Edit reminder #N directly
qremind --hide                           Select reminders to hide interactively
qremind --hide N[,N...]                  Suppress reminder(s) from notifications
qremind --unhide                         Select hidden reminders to restore interactively
qremind --unhide N[,N...]                Restore suppressed reminder(s)
qremind --delete                         Select reminders to delete interactively
qremind --delete N[,N...]               Permanently delete reminder(s)
qremind --clean                          Remove all hidden reminders and renumber
qremind --show                           Check and display any due reminders now
qremind --status                         Show config and timer/daemon status
```

### Adding a reminder

`qremind --add` walks through each field interactively:

- **Date** — choose from preset intervals (Today, 1 day, 3 days, 1 week, 2 weeks, 1/3/6 months, 1 year) or enter a date manually (`YYYYMMDD`); a selection is required
- **Include time?** — defaults to no (Enter = N); enter `y` to add a time
- **Time** — choose from presets (+1/2/4 hours, Morning, Noon, Afternoon, Evening, Night) or enter manually (`HHMM`); a selection is required
- **Topic** — free text; required
- **Description** — free text; optional

Press ESC at any prompt to cancel without saving.

### Editing a reminder

`qremind --edit` presents an arrow-key list of all reminders — use ↑/↓ to move, Enter to select, ESC to cancel. You can also go directly to a reminder with `qremind --edit N`.

Once a reminder is open, each field is pre-filled with its current value. Press Enter to keep a field unchanged, type a new value to replace it, or press ESC to cancel without saving.

### Notifications (--show)

`qremind --show` checks for due reminders and surfaces them as desktop notifications. This is what the systemd timer and daemon call automatically.

With **zenity** (default), each due reminder appears in its own dialog with four buttons:

- **Hide** — suppresses the reminder from future notifications (reversible with `--unhide`)
- **Snooze** — delays the next notification by a chosen interval; a follow-up dialog offers 30 min, 1h, 2h, 3h, 6h, 12h, or 24h
- **Delete** — permanently removes the reminder
- **Dismiss** — closes the dialog without any action

Snoozed reminders are silently skipped each time the timer fires until the snooze expires, at which point they resume firing normally.

With **notify-send**, all due reminders are sent as a single passive notification with no interactive buttons.

### Managing snoozes (--snooze)

`qremind --snooze` shows all due, unhidden reminders and their current snooze state. Use ↑/↓ to move and Space to toggle:

- On an **unsnoozed** reminder: marks it for snoozing — a duration picker appears after you confirm
- On a **snoozed** reminder: marks it for cancellation (reminder will fire on next check)

### Hiding and deleting reminders

`qremind --hide`, `qremind --unhide`, and `qremind --delete` without arguments present an interactive multi-select list — use ↑/↓ to move, Space to toggle, Enter to confirm, ESC to cancel. `--hide` only shows visible reminders; `--unhide` only shows hidden ones.

You can also target specific reminders directly using comma-separated IDs:

```sh
qremind --delete 1,4,6,10
qremind --hide 3,7,12
qremind --unhide 3,7,12
```

## Web UI

`qremind --web` starts a local web server and opens the UI in your browser:

```sh
qremind --web          # http://localhost:8765
qremind --web 9000     # custom port
```

The web UI provides full access to your reminders without the terminal:

- **Filter bar** — switch between All, Due, This Month, Upcoming, and Hidden views; each tab shows a live count
- **Add / Edit** — date and time preset buttons (Today, +1 day, +1 week, Morning, Noon, etc.) plus free-form input fields
- **Actions per reminder** — Edit, Hide/Unhide, Snooze (uses your configured `snooze_intervals`), Unsnooze, Delete
- **Dark mode** — follows your system preference automatically

The server only listens on `127.0.0.1` and reads/writes the same data files as the CLI. Press Ctrl+C in the terminal to stop it.

## Configuration

```sh
qremind --config                                       Show current config
qremind --config check_interval_minutes=30             Set check interval to 30 minutes
qremind --config notification=notify-send              Set notification style: notify-send or zenity (default)
qremind --config snooze_intervals=30m,1h,2h,3h,6h     Set snooze duration options
```

Config is stored at `~/.config/qreminder/config.json`. Reminder data (reminders, hidden list, snooze state) lives in `~/.local/share/qreminder/`, following the XDG Base Directory standard. Data files are migrated automatically from the legacy `~/.config/qReminder/` location on first run.

## Running as a daemon

**systemd user timer** (recommended — persists across reboots):

```sh
qremind --install
qremind --uninstall   # to remove
```

**GNOME autostart** (starts a daemon at login):

```sh
qremind --install-autostart
```

**Manual daemon** (current session only):

```sh
qremind --daemon &
qremind --stop
```
