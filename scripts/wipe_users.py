"""
Deletes ALL consumer user accounts and everything tied to them: posts,
DM threads, messages, media rows, reports, and read-tracking. This is
destructive and irreversible - there's no undo.

Deliberately does NOT touch:
  - admin_users (your moderator/admin logins are untouched)
  - banned_contacts (the permanent ban list survives by default, since
    it exists specifically to block a banned person from coming back -
    wiping it defeats that purpose. Pass --include-banned to also clear it.)

Usage:
    python scripts/wipe_users.py            # wipe all users + their data
    python scripts/wipe_users.py --include-banned   # also clear ban list
    python scripts/wipe_users.py --yes       # skip the confirmation prompt
"""

import sys

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.user import User
from app.models.post import Post
from app.models.dm import DMThread, Message
from app.models.media import Media
from app.models.report import Report, MessageReport, Block, ThreadRead
from app.models.banned_contact import BannedContact


def main():
    include_banned = "--include-banned" in sys.argv
    skip_confirm = "--yes" in sys.argv

    db = SessionLocal()
    user_count = db.query(User).count()

    if user_count == 0:
        print("No user accounts found - nothing to do.")
        return

    print(f"This will permanently delete {user_count} user account(s) and all their")
    print("posts, messages, media, reports, and threads.")
    print(f"Banned-contact list will be {'ALSO CLEARED' if include_banned else 'left intact'}.")
    print("Admin/moderator accounts will NOT be touched.")

    if not skip_confirm:
        confirm = input("\nType 'DELETE' to proceed: ")
        if confirm != "DELETE":
            print("Cancelled.")
            return

    # Order matters - delete leaf tables before the ones they reference.
    db.query(MessageReport).delete()
    db.query(Report).delete()
    db.query(ThreadRead).delete()
    db.query(Block).delete()
    db.query(Message).delete()   # must go before Media - Message.media_id references it
    db.query(Media).delete()
    db.query(DMThread).delete()
    db.query(Post).delete()

    if include_banned:
        db.query(BannedContact).delete()

    db.query(User).delete()

    db.commit()
    print(f"\nDone. Deleted {user_count} user account(s) and all associated data.")


if __name__ == "__main__":
    main()
