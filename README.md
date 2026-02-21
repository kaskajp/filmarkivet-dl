# filmarkivet-dl

Downloads all videos from a given category page on [filmarkivet.se](https://www.filmarkivet.se/) using [svtplay-dl](https://github.com/spaam/svtplay-dl).

Automatically paginates through all category pages, deduplicates URLs, and supports resuming interrupted sessions via a seen-file.

## Requirements

- Python 3.10+
- [svtplay-dl](https://github.com/spaam/svtplay-dl) installed and available in `PATH`

## Usage

```bash
python3 filmarkivet-dl.py
```

By default this downloads all videos from the [reklamfilm](https://www.filmarkivet.se/category/reklamfilm/) category.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--start-url URL` | `https://www.filmarkivet.se/category/reklamfilm/` | Category page to start from |
| `--sleep SECONDS` | `0.5` | Delay between downloads |
| `--page-sleep SECONDS` | `0.2` | Delay between page fetches |
| `--max-pages N` | `0` (no limit) | Stop after N pages |
| `--seen-file PATH` | `seen_urls.txt` | File tracking already-processed URLs |
| `--output-dir DIR` | `downloads` | Directory to save downloaded videos in |
| `--dry-run` | — | Print commands without running svtplay-dl |

### Examples

Preview what would be downloaded without actually downloading:

```bash
python3 filmarkivet-dl.py --dry-run
```

Download from a different category:

```bash
python3 filmarkivet-dl.py --start-url "https://www.filmarkivet.se/category/dokumentar/"
```

Save videos into a subdirectory:

```bash
python3 filmarkivet-dl.py --output-dir reklamfilm
```

Limit to the first 3 pages with a 2-second delay between downloads:

```bash
python3 filmarkivet-dl.py --max-pages 3 --sleep 2.0
```

## How it works

1. Fetches the category page HTML and extracts all `/movies/` links.
2. Detects the "next page" link via `rel="next"`, CSS class, or link text ("Nästa" / "Next").
3. For each new video URL, runs `svtplay-dl -S <url>` to download all available subtitles and the best quality stream.
4. Records processed URLs in `seen_urls.txt` so re-running the script skips already-downloaded videos.
