"""
A/B voice report - shows which voices have been used and their performance.
Run: python ab_report.py

Once you have YouTube analytics, update logs/ab_voice_log.json with
views/likes/comments for each entry to see which voice performs best.
"""

import json
from pathlib import Path
from collections import defaultdict

LOG_FILE = Path("logs/ab_voice_log.json")


def report():
    if not LOG_FILE.exists():
        print("No A/B log found yet. Run the pipeline first.")
        return

    with open(LOG_FILE) as f:
        entries = json.load(f)

    if not entries:
        print("No entries yet.")
        return

    print(f"\n{'='*60}")
    print(f"A/B VOICE TEST REPORT — {len(entries)} videos")
    print(f"{'='*60}\n")

    # Group by voice
    by_voice = defaultdict(list)
    for e in entries:
        by_voice[e["voice_name"]].append(e)

    # Summary table
    print(f"{'Voice':<20} {'Uses':>5} {'Avg Views':>10} {'Avg Likes':>10} {'Avg Comments':>13}")
    print("-" * 62)

    voice_stats = []
    for voice_name, ventries in sorted(by_voice.items()):
        uses = len(ventries)
        views_data   = [e["views"]    for e in ventries if e.get("views")    is not None]
        likes_data   = [e["likes"]    for e in ventries if e.get("likes")    is not None]
        comment_data = [e["comments"] for e in ventries if e.get("comments") is not None]

        avg_views    = sum(views_data)    / len(views_data)    if views_data    else None
        avg_likes    = sum(likes_data)    / len(likes_data)    if likes_data    else None
        avg_comments = sum(comment_data)  / len(comment_data)  if comment_data  else None

        voice_stats.append((voice_name, uses, avg_views, avg_likes, avg_comments))

        views_str    = f"{avg_views:,.0f}"    if avg_views    is not None else "no data"
        likes_str    = f"{avg_likes:,.0f}"    if avg_likes    is not None else "no data"
        comments_str = f"{avg_comments:,.0f}" if avg_comments is not None else "no data"

        print(f"{voice_name:<20} {uses:>5} {views_str:>10} {likes_str:>10} {comments_str:>13}")

    # Best performer
    ranked = [(n, v, a) for n, u, a, l, c in voice_stats if a is not None for v in [a]]
    if ranked:
        best = max(ranked, key=lambda x: x[1])
        print(f"\nBest performing voice so far: {best[0]} ({best[1]:,.0f} avg views)")

    # Recent videos
    print(f"\n{'='*60}")
    print("RECENT VIDEOS")
    print(f"{'='*60}")
    for e in entries[-10:][::-1]:
        views_str = f"{e['views']:,}" if e.get("views") is not None else "pending"
        print(f"  [{e['timestamp'][:10]}] {e['voice_name']:<20} | {e.get('title','')[:40]}")
        print(f"    views: {views_str} | category: {e.get('category','')} | type: {e.get('content_type','')}")

    print(f"\nLog file: {LOG_FILE}")
    print("Add views/likes/comments to the log to see performance rankings.\n")


if __name__ == "__main__":
    report()
