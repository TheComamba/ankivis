# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). From 1.0.0 on,
the command line interface (commands, options and their defaults) is the public API.

## [Unreleased]

## [1.0.0] - 2026-10-25

First release.

### Added
- `decks`: list the decks of an Anki collection, or select one with `--pick` or `--deck`.
  The collection is opened read-only, and a temporary copy is used if Anki has locked it.
  Anki's data folder is found on Linux, macOS and Windows, and `ANKI_BASE` overrides it.
  A single profile is detected automatically.
- `intervals`: print the cards with the largest intervals on a given date.
- `chart`: render the state of a deck on a date as a square pie chart PNG with a transparent
  background. Cards are coloured on a log scale from red (≤ 1 day) to blue (≥ 2 years),
  unlearned cards are transparent, and a legend and the learned percentage are shown.
  `--size` sets the image size.
- `export`: render one image per day from the first review up to `--until`, skipping days
  whose image already exists.
- `video`: combine the daily images into an H.264 MP4 or a looping animated GIF, with
  `--fps`, `--background`, `--from` and `--until`.
- `--version` / `-V` prints the installed version.

[Unreleased]: https://github.com/TheComamba/ankivis/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/TheComamba/ankivis/releases/tag/v1.0.0
