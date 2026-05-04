"""
Demo collectors for Reddit, Bluesky, and optional Facebook Page posts.
Used only when an authenticated user has the social_feed.demo permission.

Keywords are supplied by the client (comma-separated), not hardcoded here.
Facebook: Meta does not expose global public keyword search; we only fetch
from a single Page when FACEBOOK_ACCESS_TOKEN + FACEBOOK_PAGE_ID are set.
deployement testing
"""
from __future__ import annotations

import base64
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

# Reddit public JSON expects a real browser-style UA; matches a known-good pattern (search.json returns 200).
DEFAULT_REDDIT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# Cached Bluesky session (access JWT). Refreshed periodically when app-password auth is configured.
_bsky_jwt_cache: tuple[str, float] | None = None


def _bluesky_identifier_password() -> tuple[str | None, str | None]:
    ident = (
        os.getenv("BSKY_IDENTIFIER")
        or os.getenv("BLUESKY_IDENTIFIER")
        or os.getenv("BSKY_HANDLE")
        or os.getenv("BLUESKY_HANDLE")
    )
    pw = os.getenv("BSKY_APP_PASSWORD") or os.getenv("BLUESKY_APP_PASSWORD")
    ident = ident.strip() if ident else None
    pw = pw.strip() if pw else None
    return ident, pw


def _bluesky_login() -> tuple[str | None, str | None]:
    """
    Obtain an access JWT via com.atproto.server.createSession (app password).
    Returns (jwt, error_message). error_message is None on success.
    """
    ident, pw = _bluesky_identifier_password()
    if not ident or not pw:
        return None, None

    global _bsky_jwt_cache
    now = time.time()
    if _bsky_jwt_cache is not None:
        token, exp = _bsky_jwt_cache
        if exp > now + 30:
            return token, None

    host = (os.getenv("BSKY_PDS_HOST") or "https://bsky.social").rstrip("/")
    url = f"{host}/xrpc/com.atproto.server.createSession"
    ua = os.getenv("BLUESKY_USER_AGENT", "Sentilytics/1.0 (social demo)")
    payload = json.dumps({"identifier": ident, "password": pw}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": ua},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.warning("Bluesky createSession HTTP %s: %s", e.code, body[:500])
        return None, f"HTTP {e.code} from Bluesky login"
    except Exception as e:
        logger.warning("Bluesky createSession failed: %s", e)
        return None, str(e) or e.__class__.__name__

    token = data.get("accessJwt")
    if not token:
        return None, "Bluesky login response missing accessJwt"

    _bsky_jwt_cache = (token, now + 50 * 60)
    return token, None


def _bluesky_search_headers(access_jwt: str | None) -> dict[str, str]:
    ua = os.getenv(
        "BLUESKY_USER_AGENT",
        "Sentilytics/1.0 (campus feedback demo; contact admin)",
    )
    h: dict[str, str] = {"User-Agent": ua, "Accept": "application/json"}
    if access_jwt:
        h["Authorization"] = f"Bearer {access_jwt}"
    return h

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

MAX_SOCIAL_KEYWORDS = 40


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


def parse_keywords_csv(raw: str) -> list[str]:
    """
    Split user-supplied comma-separated keywords. Dedupes case-insensitively.
    Raises ValueError for invalid input.
    """
    out: list[str] = []
    seen: set[str] = set()
    for part in (raw or "").split(","):
        p = part.strip()
        if not p:
            continue
        if len(p) > 200:
            raise ValueError("Each keyword must be at most 200 characters")
        k = p.casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
        if len(out) > MAX_SOCIAL_KEYWORDS:
            raise ValueError(f"At most {MAX_SOCIAL_KEYWORDS} comma-separated keywords")
    if not out:
        raise ValueError("Enter at least one keyword (comma-separated)")
    return out


def _matched_label(text: str, keyword: str) -> str:
    """Prefer known uni label from post text / keyword; else use keyword for display."""
    u = match_university(text or "")
    if u:
        return u
    u2 = match_university(keyword or "")
    if u2:
        return u2
    kw = (keyword or "").strip()
    return kw[:120] if kw else "keyword"


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


def collect_bluesky(
    start: date,
    end: date,
    limit_per_keyword: int,
    keywords: list[str],
) -> tuple[list[SocialRow], list[str]]:
    warnings: list[str] = []
    rows: list[SocialRow] = []
    start_ts, end_ts = _utc_bounds(start, end)
    base = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"

    access_jwt: str | None = None
    ident, pw = _bluesky_identifier_password()
    if ident and pw:
        jwt, err = _bluesky_login()
        if err:
            warnings.append(f"Bluesky authentication failed (check BSKY_IDENTIFIER and BSKY_APP_PASSWORD): {err}")
            return [], warnings
        access_jwt = jwt

    bluesky_http_errors: list[tuple[str, int]] = []

    for kw in keywords:
        q = urllib.parse.quote(kw)
        url = f"{base}?q={q}&limit={min(limit_per_keyword, 100)}"
        try:
            data = _http_get_json(url, headers=_bluesky_search_headers(access_jwt))
        except urllib.error.HTTPError as e:
            bluesky_http_errors.append((kw, int(e.code)))
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
            label = _matched_label(text, kw)
            row = SocialRow(
                platform="Bluesky",
                channel=f"search:{kw}",
                post_id=uri or f"bsky-{author}-{rkey}",
                parent_id=None,
                post_type="post",
                university_matched=label,
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

    if bluesky_http_errors:
        codes = {c for _, c in bluesky_http_errors}
        if len(bluesky_http_errors) >= 5 and len(codes) == 1:
            only = next(iter(codes))
            warnings.append(
                f"Bluesky: {len(bluesky_http_errors)} keyword searches failed with HTTP {only}. "
                "The public AppView often returns 403 from datacenters/VPNs or when unauthenticated search is restricted. "
                "Set BSKY_IDENTIFIER (handle or email) and BSKY_APP_PASSWORD (Bluesky app password) on the server, "
                "restart the API, then try again."
            )
        else:
            for kw, code in bluesky_http_errors[:40]:
                warnings.append(f"Bluesky HTTP {code} for query {kw!r}")
            if len(bluesky_http_errors) > 40:
                warnings.append(f"... and {len(bluesky_http_errors) - 40} more Bluesky query errors")

    return rows, warnings


def _reddit_headers() -> dict[str, str]:
    custom = (os.getenv("REDDIT_USER_AGENT") or "").strip()
    ua = custom if custom else DEFAULT_REDDIT_USER_AGENT
    return {"User-Agent": ua, "Accept": "application/json"}


def collect_reddit_keyword_search_json(
    start: date,
    end: date,
    limit_per_keyword: int,
    keywords: list[str],
) -> tuple[list[SocialRow], list[str]]:
    """Public Reddit JSON — global search by keyword (no OAuth). Same pattern as search.json?q=keyword + browser-like UA."""
    warnings: list[str] = []
    rows: list[SocialRow] = []
    start_ts, end_ts = _utc_bounds(start, end)
    cap = max(5, min(limit_per_keyword, 100))
    for kw in keywords:
        q = urllib.parse.quote(kw)
        # Minimal URL shape that returns 200 + Listing/children; limit caps response size.
        url = f"https://www.reddit.com/search.json?q={q}&limit={cap}"
        try:
            data = _http_get_json(url, headers=_reddit_headers())
        except urllib.error.HTTPError as e:
            warnings.append(f"Reddit search {kw!r}: HTTP {e.code}")
            continue
        except Exception as e:
            warnings.append(f"Reddit search {kw!r}: {e}")
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
            label = _matched_label(combined, kw)
            pid = d.get("id") or ""
            permalink = d.get("permalink") or ""
            link = f"https://www.reddit.com{permalink}" if permalink else ""
            author = str(d.get("author") or "[deleted]")
            row = SocialRow(
                platform="Reddit",
                channel=f"search:{kw}",
                post_id=pid,
                parent_id=None,
                post_type="submission",
                university_matched=label,
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
    limit_per_keyword: int,
    keywords: list[str],
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
    ua = (os.getenv("REDDIT_USER_AGENT") or "").strip() or DEFAULT_REDDIT_USER_AGENT
    reddit = praw.Reddit(client_id=cid, client_secret=secret, user_agent=ua)
    reddit.read_only = True
    cap = max(5, min(limit_per_keyword, 100))
    for kw in keywords:
        try:
            for submission in reddit.subreddit("all").search(kw, sort="new", time_filter="all", limit=cap):
                if submission.created_utc < start_ts or submission.created_utc > end_ts:
                    continue
                combined_text = f"{submission.title} {submission.selftext}"
                label = _matched_label(combined_text, kw)
                channel = f"search:{kw}"
                rows.append(
                    SocialRow(
                        platform="Reddit",
                        channel=channel,
                        post_id=submission.id,
                        parent_id=None,
                        post_type="submission",
                        university_matched=label,
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
                                channel=channel,
                                post_id=comment.id,
                                parent_id=submission.id,
                                post_type="comment",
                                university_matched=label,
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
                    warnings.append(f"Reddit comments on {submission.id}: {e}")
                time.sleep(0.35)
        except Exception as e:
            warnings.append(f"Reddit search {kw!r}: {e}")
        time.sleep(1.0)
    return rows, warnings


def collect_facebook(
    start: date,
    end: date,
    limit_per_keyword: int,
    keywords: list[str],
) -> tuple[list[SocialRow], list[str]]:
    warnings: list[str] = []
    rows: list[SocialRow] = []
    token = (os.getenv("FACEBOOK_ACCESS_TOKEN") or "").strip()
    page_id = (os.getenv("FACEBOOK_PAGE_ID") or "").strip()
    graph_ver = (os.getenv("FACEBOOK_GRAPH_VERSION") or "v21.0").strip().lstrip("/")
    if not token or not page_id:
        warnings.append(
            "Facebook: not connected (set FACEBOOK_ACCESS_TOKEN and FACEBOOK_PAGE_ID). "
            "Meta Graph API does not provide global public keyword search; only Page posts you administer can be fetched."
        )
        return [], warnings

    start_ts, end_ts = _utc_bounds(start, end)
    cap = max(5, min(limit_per_keyword, 50))
    kws_lower = [k.lower() for k in keywords if k.strip()]

    q = urllib.parse.urlencode(
        {
            "fields": "id,message,created_time,permalink_url",
            "limit": str(cap),
            "access_token": token,
        }
    )
    url = f"https://graph.facebook.com/{graph_ver}/{urllib.parse.quote(page_id, safe='')}/posts?{q}"
    try:
        data = _http_get_json(url)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = str(e)
        warnings.append(f"Facebook Graph API HTTP {e.code}: {err_body[:240]}")
        return [], warnings
    except Exception as e:
        warnings.append(f"Facebook: {e}")
        return [], warnings

    for item in data.get("data") or []:
        msg = (item.get("message") or "").strip()
        created_s = item.get("created_time") or ""
        try:
            dt = datetime.strptime(created_s, "%Y-%m-%dT%H:%M:%S%z")
            ts = dt.timestamp()
        except Exception:
            try:
                dt = datetime.fromisoformat(created_s.replace("Z", "+00:00"))
                ts = dt.timestamp()
            except Exception:
                continue
        if not (start_ts <= ts <= end_ts):
            continue
        if kws_lower:
            ml = msg.lower()
            if not any(k in ml for k in kws_lower):
                continue
        pid = str(item.get("id") or "")
        link = (item.get("permalink_url") or "").strip()
        if not link and pid:
            link = f"https://www.facebook.com/{pid.replace('_', '/posts/')}"
        label = _matched_label(msg, keywords[0] if keywords else "")
        row = SocialRow(
            platform="Facebook",
            channel=f"page:{page_id}",
            post_id=pid,
            parent_id=None,
            post_type="page_post",
            university_matched=label,
            author=page_id,
            title=None,
            content=msg or "(no text)",
            timestamp_utc=dt.astimezone(timezone.utc).isoformat(),
            score=0,
            num_comments=None,
            url=link,
            import_key=_import_key("facebook", pid, msg),
        )
        rows.append(row)

    if not rows:
        warnings.append(
            "Facebook: no Page posts matched your date range and keywords. "
            "Check token permissions (pages_read_engagement), Page id, and that posts contain the keywords."
        )
    return rows, warnings


def merge_preview(
    start: date,
    end: date,
    platforms: list[str],
    include_reddit_comments: bool,
    limit_per_subreddit: int,
    keywords: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Aggregate rows for API preview (deduped by import_key)."""
    warnings: list[str] = []
    all_rows: list[SocialRow] = []
    plats = {p.lower().strip() for p in platforms}
    if "reddit" in plats:
        if include_reddit_comments:
            r_rows, r_warn = collect_reddit_praw_comments(start, end, limit_per_subreddit, keywords)
            all_rows.extend(r_rows)
            warnings.extend(r_warn)
        else:
            r_rows, r_warn = collect_reddit_keyword_search_json(start, end, limit_per_subreddit, keywords)
            all_rows.extend(r_rows)
            warnings.extend(r_warn)
    if "bluesky" in plats:
        b_rows, b_warn = collect_bluesky(
            start,
            end,
            limit_per_keyword=min(30, limit_per_subreddit),
            keywords=keywords,
        )
        all_rows.extend(b_rows)
        warnings.extend(b_warn)
    if "facebook" in plats:
        f_rows, f_warn = collect_facebook(start, end, limit_per_subreddit, keywords)
        all_rows.extend(f_rows)
        warnings.extend(f_warn)
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


# --- live connectivity probes (cached; used by /integrations/social/status) ---
_SOCIAL_PROBE_CACHE: tuple[float, dict[str, bool]] | None = None
SOCIAL_PROBE_TTL_SEC = 45.0


def _probe_bluesky_live() -> bool:
    """True if AppView search returns JSON (uses app-password session when configured)."""
    access_jwt: str | None = None
    ident, pw = _bluesky_identifier_password()
    if ident and pw:
        jwt, err = _bluesky_login()
        if err:
            return False
        access_jwt = jwt
    url = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=test&limit=1"
    try:
        data = _http_get_json(url, headers=_bluesky_search_headers(access_jwt))
        return isinstance(data, dict) and isinstance(data.get("posts"), list)
    except Exception:
        return False


def _probe_reddit_public_live() -> bool:
    """True if anonymous Reddit search.json responds (same UA + URL shape as collect_reddit_keyword_search_json)."""
    urls = [
        "https://www.reddit.com/search.json?q=test&limit=5",
        "https://old.reddit.com/search.json?q=test&limit=5",
    ]
    for url in urls:
        try:
            data = _http_get_json(url, headers=_reddit_headers())
            if isinstance(data, dict) and isinstance((data.get("data") or {}).get("children"), list):
                return True
        except Exception:
            continue
    return False


def _probe_reddit_oauth_live() -> bool:
    """True if client_id/secret obtain an app-only access_token (application-only OAuth)."""
    cid = (os.getenv("REDDIT_CLIENT_ID") or "").strip()
    sec = (os.getenv("REDDIT_CLIENT_SECRET") or "").strip()
    if not cid or not sec:
        return False
    auth_b64 = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    ua = _reddit_headers()["User-Agent"]
    body = b"grant_type=client_credentials"
    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=body,
        headers={
            "Authorization": f"Basic {auth_b64}",
            "User-Agent": ua,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            j = json.loads(resp.read().decode("utf-8"))
        return bool(j.get("access_token"))
    except Exception:
        return False


def _probe_facebook_live() -> bool:
    """True if Graph can read the configured Page with the given token."""
    token = (os.getenv("FACEBOOK_ACCESS_TOKEN") or "").strip()
    page_id = (os.getenv("FACEBOOK_PAGE_ID") or "").strip()
    if not token or not page_id:
        return False
    ver = (os.getenv("FACEBOOK_GRAPH_VERSION") or "v21.0").strip().lstrip("/")
    q = urllib.parse.urlencode({"fields": "id", "access_token": token})
    url = f"https://graph.facebook.com/{ver}/{urllib.parse.quote(page_id, safe='')}?{q}"
    try:
        data = _http_get_json(url)
        return isinstance(data, dict) and bool(data.get("id"))
    except Exception:
        return False


def get_live_social_connection_flags() -> dict[str, bool]:
    """Short-lived cache so the UI can show real reachability, not just env presence."""
    global _SOCIAL_PROBE_CACHE
    now = time.time()
    if _SOCIAL_PROBE_CACHE is not None and (now - _SOCIAL_PROBE_CACHE[0]) < SOCIAL_PROBE_TTL_SEC:
        return dict(_SOCIAL_PROBE_CACHE[1])

    bs = _probe_bluesky_live()
    rs = _probe_reddit_public_live()
    ro = _probe_reddit_oauth_live()
    fb = _probe_facebook_live()
    out: dict[str, bool] = {
        "bluesky_connected": bs,
        "reddit_search_connected": rs,
        "reddit_oauth_connected": ro,
        "reddit_connected": rs or ro,
        "facebook_connected": fb,
    }
    _SOCIAL_PROBE_CACHE = (now, out)
    return dict(out)


def clear_social_probe_cache() -> None:
    global _SOCIAL_PROBE_CACHE
    _SOCIAL_PROBE_CACHE = None
