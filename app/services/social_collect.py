"""
Demo collectors for public Reddit (.json) and Bluesky (public XRPC) posts.
Used only when an authenticated user has the social_feed.demo permission.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger("voxintent")

AUSTRALIAN_UNIS: dict[str, list[str]] = {
    "University of Melbourne": ["unimelb", "university of melbourne", "melbourne uni"],
    "University of Sydney": ["usyd", "university of sydney", "sydney uni"],
    "UNSW": ["unsw", "university of new south wales"],
    "Monash University": ["monash", "monash uni"],
    "ANU": ["anu", "australian national university"],
    "University of Queensland": ["uq", "university of queensland", "uqld"],
    "UWA": ["uwa", "university of western australia"],
    "University of Adelaide": ["adelaide uni", "university of adelaide"],
    "UTS": ["uts", "university of technology sydney"],
    "Macquarie University": ["macquarie uni", "macquarie university"],
    "QUT": ["qut", "queensland university of technology"],
    "RMIT": ["rmit"],
    "Deakin University": ["deakin uni", "deakin university"],
    "Griffith University": ["griffith uni", "griffith university"],
    "La Trobe University": ["la trobe", "latrobe"],
    "University of Wollongong": ["uow", "wollongong uni"],
    "Curtin University": ["curtin uni", "curtin university"],
}

UNI_SUBREDDITS: list[str] = [
    "unimelb",
    "usyd",
    "unsw",
    "monash",
    "anu",
    "uqreddit",
    "uwa",
    "adelaide",
    "uts",
    "macquarieuni",
    "qut",
    "rmit",
    "deakin",
    "griffithuni",
    "latrobeuni",
    "uow",
    "curtin",
    "australia",
    "australianteachers",
    "ausfinance",
    "getstudying",
]


def _utc_bounds(d0: date, d1: date) -> tuple[float, float]:
    start = datetime(d0.year, d0.month, d0.day, tzinfo=timezone.utc)
    end = datetime(d1.year, d1.month, d1.day, 23, 59, 59, tzinfo=timezone.utc)
    return start.timestamp(), end.timestamp()


def match_university(text: str) -> str | None:
    text_lower = (text or "").lower()
    padded = f" {text_lower} "
    for uni, keywords in AUSTRALIAN_UNIS.items():
        for kw in keywords:
            if f" {kw} " in padded or text_lower.startswith(kw + " ") or text_lower.endswith(" " + kw) or text_lower == kw:
                return uni
    return None


def _import_key(platform: str, post_id: str, content: str) -> str:
    h = hashlib.sha256(f"{platform}|{post_id}|{content[:400]}".encode("utf-8", errors="replace")).hexdigest()
    return h[:48]


def _http_get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


@dataclass
class SocialRow:
    platform: str
    channel: str
    post_id: str
    parent_id: str | None
    post_type: str
    university_matched: str
    author: str
    title: str | None
    content: str
    timestamp_utc: str
    score: int
    num_comments: int | None
    url: str
    import_key: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def collect_bluesky(start: date, end: date, limit_per_keyword: int = 25) -> tuple[list[SocialRow], list[str]]:
    warnings: list[str] = []
    rows: list[SocialRow] = []
    start_ts, end_ts = _utc_bounds(start, end)
    base = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
    for uni, keywords in AUSTRALIAN_UNIS.items():
        for kw in keywords:
            q = urllib.parse.quote(kw)
            url = f"{base}?q={q}&limit={min(limit_per_keyword, 100)}"
            try:
                data = _http_get_json(url)
            except urllib.error.HTTPError as e:
                warnings.append(f"Bluesky HTTP {e.code} for query {kw!r}")
                continue
            except Exception as e:
                warnings.append(f"Bluesky error for {kw!r}: {e}")
                continue
            for item in data.get("posts") or []:
                record = item.get("record") or {}
                created = record.get("createdAt") or ""
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    ts = dt.timestamp()
                except Exception:
                    continue
                if not (start_ts <= ts <= end_ts):
                    continue
                text = record.get("text") or ""
                author = (item.get("author") or {}).get("handle") or "unknown"
                uri = item.get("uri") or ""
                rkey = uri.split("/")[-1] if uri else ""
                post_url = f"https://bsky.app/profile/{author}/post/{rkey}" if author and rkey else ""
                row = SocialRow(
                    platform="Bluesky",
                    channel="search",
                    post_id=uri or f"bsky-{author}-{rkey}",
                    parent_id=None,
                    post_type="post",
                    university_matched=uni,
                    author=author,
                    title=None,
                    content=text,
                    timestamp_utc=dt.astimezone(timezone.utc).isoformat(),
                    score=int(item.get("likeCount") or 0),
                    num_comments=int(item.get("replyCount") or 0),
                    url=post_url,
                    import_key=_import_key("bluesky", uri or rkey, text),
                )
                rows.append(row)
            time.sleep(0.25)
    return rows, warnings


def _reddit_headers() -> dict[str, str]:
    ua = os.getenv("REDDIT_USER_AGENT", "SentilyticsUniDemo/1.0 (research demo; contact local admin)")
    return {"User-Agent": ua}


def collect_reddit_json(
    start: date,
    end: date,
    limit_per_sub: int,
    subreddits: list[str] | None = None,
) -> tuple[list[SocialRow], list[str]]:
    """Public Reddit JSON — submissions only (no OAuth)."""
    warnings: list[str] = []
    rows: list[SocialRow] = []
    start_ts, end_ts = _utc_bounds(start, end)
    subs = [s.lower().strip() for s in (subreddits or UNI_SUBREDDITS)]
    cap = max(5, min(limit_per_sub, 100))
    for sub in subs:
        url = f"https://www.reddit.com/r/{urllib.parse.quote(sub)}/new.json?limit={cap}&raw_json=1"
        try:
            data = _http_get_json(url, headers=_reddit_headers())
        except urllib.error.HTTPError as e:
            warnings.append(f"Reddit r/{sub}: HTTP {e.code}")
            continue
        except Exception as e:
            warnings.append(f"Reddit r/{sub}: {e}")
            continue
        for child in (data.get("data") or {}).get("children") or []:
            d = child.get("data") or {}
            if child.get("kind") != "t3":
                continue
            created = float(d.get("created_utc") or 0)
            if not (start_ts <= created <= end_ts):
                continue
            title = d.get("title") or ""
            body = d.get("selftext") or ""
            combined = f"{title} {body}".strip()
            uni = match_university(combined) or match_university(sub) or sub
            pid = d.get("id") or ""
            permalink = d.get("permalink") or ""
            link = f"https://www.reddit.com{permalink}" if permalink else ""
            author = str(d.get("author") or "[deleted]")
            row = SocialRow(
                platform="Reddit",
                channel=sub,
                post_id=pid,
                parent_id=None,
                post_type="submission",
                university_matched=uni if isinstance(uni, str) else str(uni),
                author=author,
                title=title or None,
                content=body if body else title,
                timestamp_utc=datetime.fromtimestamp(created, tz=timezone.utc).isoformat(),
                score=int(d.get("score") or 0),
                num_comments=int(d.get("num_comments") or 0),
                url=link,
                import_key=_import_key("reddit", pid, combined),
            )
            rows.append(row)
        time.sleep(1.1)
    return rows, warnings


def collect_reddit_praw_comments(
    start: date,
    end: date,
    limit_per_sub: int,
    subreddits: list[str] | None = None,
) -> tuple[list[SocialRow], list[str]]:
    warnings: list[str] = []
    rows: list[SocialRow] = []
    cid = os.getenv("REDDIT_CLIENT_ID")
    secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not cid or not secret:
        return [], ["Reddit comments require REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (script app)."]
    try:
        import praw  # type: ignore
    except ImportError:
        return [], ["praw is not installed; pip install praw for Reddit comment collection."]
    start_ts, end_ts = _utc_bounds(start, end)
    ua = os.getenv("REDDIT_USER_AGENT", "SentilyticsUniDemo/1.0")
    reddit = praw.Reddit(client_id=cid, client_secret=secret, user_agent=ua)
    reddit.read_only = True
    subs = [s.lower().strip() for s in (subreddits or UNI_SUBREDDITS)]
    cap = max(5, min(limit_per_sub, 100))
    for sub in subs:
        try:
            subreddit = reddit.subreddit(sub)
            for submission in subreddit.new(limit=cap):
                if submission.created_utc < start_ts:
                    break
                if submission.created_utc > end_ts:
                    continue
                combined_text = f"{submission.title} {submission.selftext}"
                uni = match_university(combined_text) or match_university(sub) or sub
                rows.append(
                    SocialRow(
                        platform="Reddit",
                        channel=sub,
                        post_id=submission.id,
                        parent_id=None,
                        post_type="submission",
                        university_matched=uni if isinstance(uni, str) else str(uni),
                        author=str(submission.author) if submission.author else "[deleted]",
                        title=submission.title,
                        content=submission.selftext or submission.title,
                        timestamp_utc=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc).isoformat(),
                        score=int(submission.score),
                        num_comments=int(submission.num_comments or 0),
                        url=f"https://www.reddit.com{submission.permalink}",
                        import_key=_import_key("reddit", submission.id, combined_text),
                    )
                )
                try:
                    submission.comments.replace_more(limit=0)
                    for comment in submission.comments.list():
                        if not (start_ts <= comment.created_utc <= end_ts):
                            continue
                        rows.append(
                            SocialRow(
                                platform="Reddit",
                                channel=sub,
                                post_id=comment.id,
                                parent_id=submission.id,
                                post_type="comment",
                                university_matched=uni if isinstance(uni, str) else str(uni),
                                author=str(comment.author) if comment.author else "[deleted]",
                                title=None,
                                content=comment.body or "",
                                timestamp_utc=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc).isoformat(),
                                score=int(comment.score or 0),
                                num_comments=None,
                                url=f"https://www.reddit.com{comment.permalink}",
                                import_key=_import_key("reddit", comment.id, comment.body or ""),
                            )
                        )
                except Exception as e:
                    warnings.append(f"r/{sub} comments: {e}")
                time.sleep(0.35)
        except Exception as e:
            warnings.append(f"Reddit r/{sub}: {e}")
    return rows, warnings


def merge_preview(
    start: date,
    end: date,
    platforms: list[str],
    include_reddit_comments: bool,
    limit_per_subreddit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Aggregate rows for API preview (deduped by import_key)."""
    warnings: list[str] = []
    all_rows: list[SocialRow] = []
    plats = {p.lower().strip() for p in platforms}
    if "reddit" in plats:
        if include_reddit_comments:
            r_rows, r_warn = collect_reddit_praw_comments(start, end, limit_per_subreddit)
            all_rows.extend(r_rows)
            warnings.extend(r_warn)
        else:
            r_rows, r_warn = collect_reddit_json(start, end, limit_per_subreddit)
            all_rows.extend(r_rows)
            warnings.extend(r_warn)
            if not os.getenv("REDDIT_CLIENT_ID"):
                warnings.append("Reddit is using the public JSON API (submissions only). Enable OAuth + praw for comments.")
    if "bluesky" in plats:
        b_rows, b_warn = collect_bluesky(start, end, limit_per_keyword=min(30, limit_per_subreddit))
        all_rows.extend(b_rows)
        warnings.extend(b_warn)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in all_rows:
        if row.import_key in seen:
            continue
        seen.add(row.import_key)
        unique.append(row.as_dict())
    max_rows = 600
    if len(unique) > max_rows:
        warnings.append(f"Preview capped at {max_rows} rows (unique by import_key).")
        unique = unique[:max_rows]
    return unique, warnings
