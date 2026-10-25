# ankivis
Visualise learning progress for an Anki deck.

## Scripts

All scripts can be called from any directory and use the virtual environment in `.venv/`.

| Script | Purpose |
|---|---|
| `_scripts/setup.sh` | Create `.venv` and install ankivis with dev dependencies |
| `_scripts/run.sh [ARGS]` | Run ankivis, e.g. `_scripts/run.sh --help` |
| `_scripts/lint.sh [--fix]` | Run ruff (lint + format check); `--fix` applies fixes and reformats |
| `_scripts/test.sh [PYTEST ARGS]` | Run `lint.sh`, then pytest |
| `_scripts/update.sh` | Upgrade all dependencies to the newest allowed versions |

Shared logic lives in `_scripts/lib/shared.sh`.

## Usage

```sh
_scripts/setup.sh
_scripts/run.sh --help
```

### Decks

The collection is opened read-only. If Anki is running and the database is locked, ankivis
reads from a temporary copy instead. It reads `<Anki data folder>/<profile>/collection.anki2`,
where the Anki data folder is:

| Platform | Anki data folder |
|---|---|
| Linux | `$XDG_DATA_HOME/Anki2` (default `~/.local/share/Anki2`) |
| macOS | `~/Library/Application Support/Anki2` |
| Windows | `%APPDATA%\Anki2` |

Like Anki itself, the `ANKI_BASE` environment variable overrides this folder on all platforms.
If there is only one profile, it is detected automatically, including localised names such as
`Benutzer 1`. Otherwise pass `--profile`.

```sh
_scripts/run.sh decks                                   # numbered list of all decks
_scripts/run.sh decks --profile "Alice"                 # another Anki profile
_scripts/run.sh decks --collection path/to/collection.anki2
_scripts/run.sh decks --pick                            # pick interactively (number, name or id)
_scripts/run.sh decks --deck "Spanish::Verbs"           # select by name or id
_scripts/run.sh decks --deck Spanish --no-subdecks      # exclude subdecks
```

### Pie chart

`chart` renders the state of a deck at the end of a day as a pie chart PNG (800×800 px,
transparent background). Each card is a slice; cards are sorted by interval, so the colours
form a gradient: red (≤ 1 day) → orange → yellow → green → blue (≥ 2 years), on a log scale.
Cards that exist but have not been learned yet are transparent. A legend below the pie shows
the colours of representative intervals (1 day, 1 week, 1 month, 3 months, 1 year, 2 years,
unlearned).

```sh
_scripts/run.sh chart --deck Spanish                            # today → ./YYYY-MM-DD.png
_scripts/run.sh chart --deck Spanish --date 2024-03-10 --out spanish.png
```

### Daily images

`export` renders one pie chart per day into a directory, from the day of the deck's first
review up to the date given with `--until` (inclusive). It defaults to yesterday, because
today is not over yet; dates in the future are rejected. Files are named `YYYY-MM-DD.png`.
Days whose image already exists are skipped, so running the command again only adds the new
days. To re-render a day, delete its image.

```sh
_scripts/run.sh export --deck Spanish --out frames/                     # up to yesterday
_scripts/run.sh export --deck Spanish --out frames/ --until 2024-03-10
```

### Video

`video` combines the `YYYY-MM-DD.png` images of a directory into an H.264 MP4 video or a
looping animated GIF, one frame per day in chronological order (10 frames per second by
default). Other files in the directory are ignored. The output has no transparency, so
transparent areas are filled with the `--background` colour (default white). `--from` and
`--until` restrict the date range.

The format is chosen with `--format mp4|gif`; without it, it follows the extension of `--out`
(`.gif` → GIF), otherwise MP4. The video is written to `progress.mp4` (or `progress.gif`)
inside the `--in` directory unless `--out` is given. GIFs are limited to 256 colours per frame
and at most 50 fps, and are usually much larger than an MP4 – but they play everywhere,
e.g. embedded in a README. ffmpeg is bundled through `imageio[ffmpeg]`; no system
installation is needed.

```sh
_scripts/run.sh video --in frames/                                      # → frames/progress.mp4
_scripts/run.sh video --in frames/ --format gif                         # → frames/progress.gif
_scripts/run.sh video --in frames/ --out spanish.gif --fps 20
_scripts/run.sh video --in frames/ --out spanish.mp4 --fps 30 --background "#202020"
_scripts/run.sh video --in frames/ --from 2024-01-01 --until 2024-12-31
```

### Disclaimer

Almost all of the code in this repository is generated. The human owner merely provided guidance, steering, and casual PR reviews. This seems an appropriate working model for an inconsequential toy project.
