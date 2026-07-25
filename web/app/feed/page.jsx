"use client";

import PostCard from "../components/PostCard";

const MOCK_POSTS = [
  {
    code: "0142",
    bodyText: "Looking for someone to grab coffee and talk film photography. No pressure, just conversation.",
    locationLabel: "STONE TOWN",
    intentTags: ["FRIENDS", "CASUAL"],
  },
  {
    code: "0143",
    bodyText: "New in town, want to meet people who are into diving and boat trips on weekends.",
    locationLabel: "NUNGWI",
    intentTags: ["ACTIVITY-PARTNER"],
  },
];

export default function FeedPage() {
  return (
    <main className="min-h-screen bg-bg px-4 py-6 max-w-md mx-auto">
      <header className="flex items-center justify-between pb-6 border-b border-line mb-6">
        <span className="font-mono text-sm tracking-widest uppercase">Liberchat</span>
        <button className="label border border-line px-3 py-2">New post</button>
      </header>

      <div className="flex flex-col gap-3">
        {MOCK_POSTS.map((post) => (
          <PostCard key={post.code} post={post} />
        ))}
      </div>
    </main>
  );
}
