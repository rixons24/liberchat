from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.post import Post, PostStatus
from app.models.user import User
from app.schemas.post import PostCreate, PostOut

router = APIRouter()


@router.get("/feed", response_model=list[PostOut])
async def get_feed(db: Session = Depends(get_db), limit: int = 50):
    posts = (
        db.query(Post)
        .filter(Post.status == PostStatus.active, Post.expires_at > datetime.utcnow())
        .order_by(Post.created_at.desc())
        .limit(limit)
        .all()
    )
    return posts


@router.post("/", response_model=PostOut)
async def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = Post(
        author_id=current_user.id,
        body_text=payload.body_text,
        intent_tags=payload.intent_tags,
        location_label=payload.location_label,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}")
async def delete_post(
    post_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).get(post_id)
    if not post or post.author_id != current_user.id:
        raise HTTPException(status_code=404, detail="Post not found.")
    # Soft-delete only — DM threads originating from this post stay alive.
    post.status = PostStatus.deleted_by_author
    post.deleted_at = datetime.utcnow()
    db.commit()
    return {"message": "Post removed from feed."}
