"""Generate the small static landing page published by GitHub Pages."""

from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

from scholar2podcast.feed import FeedError, load_episodes


def generate_index(episodes_dir: Path, index_path: Path) -> Path:
    """Build a readable HTML page containing every podcast episode."""

    episodes = load_episodes(episodes_dir)
    if not episodes:
        raise FeedError(f"No episodes were found in {episodes_dir}.")
    cards: list[str] = []
    for episode in episodes:
        author = escape(episode.author or "Unknown author")
        description = escape(episode.description or "No description available.")
        audio_url = f"episodes/{quote(episode.audio_path.name)}"
        cards.append(
            f"""    <article>
      <h2>{escape(episode.title)}</h2>
      <p class="muted">{author} · {episode.published.strftime('%B %-d, %Y')}</p>
      <p>{description}</p>
      <audio controls preload="metadata">
        <source src="{audio_url}" type="audio/mpeg">
      </audio>
      <p><a href="{escape(episode.source_url)}">View the original Scholar page</a></p>
    </article>"""
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Scholar2Podcast</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ max-width: 48rem; margin: 0 auto; padding: 3rem 1.25rem; line-height: 1.55; }}
    article {{ border: 1px solid #8886; border-radius: 1rem; padding: 1.5rem; margin: 1.25rem 0; }}
    h1, h2 {{ line-height: 1.2; }}
    audio {{ width: 100%; margin: 1rem 0; }}
    a {{ color: #3978d4; }}
    .muted {{ opacity: .72; }}
  </style>
</head>
<body>
  <header>
    <h1>Scholar2Podcast</h1>
    <p>A personal podcast feed generated from Scholar lectures.</p>
    <p><a href="feed.xml">Open the podcast RSS feed</a></p>
  </header>
  <main>
{chr(10).join(cards)}
  </main>
</body>
</html>
"""
    temporary = index_path.with_suffix(index_path.suffix + ".part")
    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(document, encoding="utf-8")
        temporary.replace(index_path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise FeedError(f"Could not write landing page: {exc}") from exc
    return index_path

