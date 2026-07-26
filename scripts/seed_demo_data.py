"""
Seeds a few demo accounts and posts for testing. Bypasses OTP by
inserting directly into the database rather than going through the
real SMS-verification flow — this is a dev/testing convenience only,
not something that should run against a production database with real
users on it.

Usage (locally or via Render Shell):
    python scripts/seed_demo_data.py
"""

import sys
import uuid
from datetime import datetime, timedelta, UTC

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.user import User
from app.models.post import Post
from app.services import auth_service

DEMO_USERS = [
    {"handle": "DemoStoneTown", "phone": "+255700111001", "password": "demoPassword123"},
    {"handle": "DemoNungwi", "phone": "+255700111002", "password": "demoPassword123"},
    {"handle": "DemoZanziGuy", "phone": "+255700111003", "password": "demoPassword123"},
]

DEMO_POSTS = [
    {
        "user_idx": 0,
        "body_text": "Looking for someone to grab coffee and talk film photography. No pressure, just conversation.",
        "location_label": "STONE TOWN",
        "intent_tags": ["FRIENDS", "CASUAL"],
    },
    {
        "user_idx": 1,
        "body_text": "New in town, want to meet people who are into diving and boat trips on weekends.",
        "location_label": "NUNGWI",
        "intent_tags": ["ACTIVITY"],
    },
    {
        "user_idx": 2,
        "body_text": "Anyone up for a beach volleyball group on Saturdays? Casual, all levels welcome.",
        "location_label": "STONE TOWN",
        "intent_tags": ["ACTIVITY", "CASUAL"],
    },
    {
        "user_idx": 0,
        "body_text": "Looking for a language exchange partner — I speak English and Swahili, want to practice French.",
        "location_label": "STONE TOWN",
        "intent_tags": ["FRIENDS"],
    },
]


def main():
    db = SessionLocal()

    created_users = []
    for u in DEMO_USERS:
        contact_hash = auth_service.hash_contact_ref(u["phone"])
        existing = db.query(User).filter_by(contact_ref_hash=contact_hash).first()
        if existing:
            print(f"User '{u['handle']}' already exists, reusing.")
            created_users.append(existing)
            continue

        user = User(
            handle=u["handle"],
            contact_ref_hash=contact_hash,
            dob_attested=datetime(1995, 1, 1, tzinfo=UTC),
            age_gate_accepted_at=datetime.now(UTC),
            phone_verified_at=datetime.now(UTC),
            password_hash=auth_service.hash_password(u["password"]),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        created_users.append(user)
        print(f"Created demo user: {u['handle']} (phone: {u['phone']}, password: {u['password']})")

    for p in DEMO_POSTS:
        author = created_users[p["user_idx"]]
        existing_post = db.query(Post).filter_by(author_id=author.id, body_text=p["body_text"]).first()
        if existing_post:
            continue
        post = Post(
            author_id=author.id,
            body_text=p["body_text"],
            location_label=p["location_label"],
            intent_tags=p["intent_tags"],
        )
        db.add(post)

    db.commit()
    print(f"\nSeeded {len(created_users)} users and {len(DEMO_POSTS)} posts.")
    print("You can log in as any demo user with their phone number + password above.")


if __name__ == "__main__":
    main()
