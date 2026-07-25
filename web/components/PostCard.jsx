export default function PostCard({ post }) {
  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label">POST / {post.code}</span>
        <span className="label">{post.locationLabel || "NO LOCATION SET"}</span>
      </div>

      <p className="text-[15px] leading-relaxed text-ink">{post.bodyText}</p>

      <div className="flex items-center justify-between pt-2 border-t border-line">
        <div className="flex gap-2">
          {post.intentTags.map((tag) => (
            <span key={tag} className="label border border-line px-2 py-1">
              {tag}
            </span>
          ))}
        </div>
        <button className="btn-secondary">Respond</button>
      </div>
    </div>
  );
}
