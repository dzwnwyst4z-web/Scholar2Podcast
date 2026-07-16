# Scholar2Podcast

Scholar2Podcast is a personal-use, Mac-first command-line tool that turns a
Scholar/Digital Commons item into a podcast-quality MP3 with stored episode
metadata and a private podcast RSS feed.

## Milestones 1–4: Download, MP3 creation, metadata, and RSS

The command downloads a Scholar page, discovers its underlying media link,
streams the video into `downloads/`, then uses `ffmpeg` to extract a 128 kbps,
44.1 kHz MP3 into `episodes/`. The lecture title is preserved as the readable
MP3 filename and embedded as an ID3 title tag.

Scholar2Podcast also extracts the author, description, and publication date
when Digital Commons provides them. These values are embedded in the MP3 and
stored in a readable JSON file beside it, ready for RSS generation.

After each successful episode, `feed.xml` is regenerated from every JSON/MP3
pair in `episodes/`. The default enclosure URLs target a local test server. Use
`--base-url` (or `SCHOLAR2PODCAST_BASE_URL`) once the files are hosted.

### Setup (macOS)

Python 3.12 or newer and `ffmpeg` are required.

```bash
brew install ffmpeg
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

### Run

```bash
scholar2podcast https://scholar.csl.edu/bible_film_christ_figures/8/
```

Choose another destination directory with `--output-dir`:

```bash
scholar2podcast URL --output-dir ~/Downloads
```

Choose another MP3 destination with `--episodes-dir`:

```bash
scholar2podcast URL --episodes-dir ~/Podcasts/Scholar2Podcast
```

Generate hosting-ready URLs during the normal workflow:

```bash
scholar2podcast URL --base-url https://podcast.example.com/
```

To test the current feed locally:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000/feed.xml` in a browser or podcast validator.

### Free hosting with GitHub Pages

This repository can be served directly from its `main` branch. For the current
project repository, use this permanent base URL when generating episodes:

```bash
export SCHOLAR2PODCAST_BASE_URL=https://dzwnwyst4z-web.github.io/Scholar2Podcast/
scholar2podcast URL
```

The included `.nojekyll` file makes GitHub Pages serve the generated files
without running Jekyll. Episode MP3 and JSON files are tracked so Pages can
publish them; original videos in `downloads/` remain local and ignored.

### Cloud processing for iPhone Shortcuts

The `Process Scholar URL` GitHub Actions workflow accepts a Scholar page URL
and performs the complete workflow on a GitHub runner. It validates that the
input is an HTTPS `.edu` URL, prevents duplicate episodes, installs the package,
downloads and converts the lecture, deletes the source video, regenerates the
RSS and landing page, and commits the published files.

Run it manually from the repository's **Actions** tab before connecting an
iPhone Shortcut. The Shortcut will eventually call the same workflow-dispatch
API with a narrowly scoped GitHub token.

Existing files are not overwritten unless `--overwrite` is supplied.

### Test

```bash
python -m unittest discover -s tests -v
```

## Why this structure?

- `src/scholar2podcast/` keeps importable application code separate from tests
  and downloaded data.
- `downloads/` is the Milestone 1 destination and is ignored by Git; generated
  media should never inflate the repository.
- `episodes/` is the Milestone 2 MP3 destination and is also ignored by Git.
- `ffmpeg` is invoked as a subprocess rather than wrapped by another Python
  package, keeping conversion explicit and dependency-free.
- `requests` provides reliable streamed HTTP downloads and Beautiful Soup makes
  inconsistent Digital Commons HTML safer to inspect than string matching.
- The CLI uses the standard library (`argparse`, `pathlib`, and `logging` is not
  needed yet), avoiding a framework and keeping the application easy to audit.
