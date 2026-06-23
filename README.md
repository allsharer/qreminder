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
qremind --edit N                         Edit reminder #N
qremind --hide N[,N...]                  Suppress reminder(s) from notifications
qremind --unhide N[,N...]                Restore suppressed reminder(s)
qremind --delete N[,N...]               Permanently delete reminder(s)
qremind --clean                          Remove all hidden reminders and renumber
qremind --show                           Check and display any due reminders now
qremind --status                         Show config and timer/daemon status
```

### Editing a reminder

`qremind --edit N` opens an interactive prompt for each field of reminder #N, pre-filled with the current value. Press Enter to keep a field unchanged, type a new value to replace it, or press ESC to cancel without saving.

### Bulk operations

Multiple reminders can be targeted in one call using comma-separated IDs:

```sh
qremind --delete 1,4,6,10
qremind --hide 3,7,12
qremind --unhide 3,7,12
```

## Configuration

```sh
qremind --config                              Show current config
qremind --config check_interval_minutes=30   Set check interval to 30 minutes
qremind --config notification=notify-send     Use notify-send instead of zenity
```

Config is stored at `~/.config/qreminder/config.json`. Reminder data lives in `~/.config/qReminder/`.

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
