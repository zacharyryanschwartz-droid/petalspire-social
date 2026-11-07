# petalspire-social

Public hosting for Petalspire's short social video clips (Facebook/Instagram Reels, X video), served by GitHub Pages at
https://zacharyryanschwartz-droid.github.io/petalspire-social/

Future posts must use `videos/index.json` entries whose `future_posting` is `use`:

- `videos/v2026-11-07-theme-a-r1/*.mp4`: 1080x1920 (9:16), H.264 + AAC, 30 fps, faststart, 4-30 s, under 25 MB. The opening half-second is the legacy frame at 1.0 s, so the cover is not the black fade. Audio is `audio/petalspire-theme-a.mp3` from 0.000 s. That slice is not a reviewed lyrical excerpt.
- `videos/v2026-11-07-theme-a-r1/covers/*.jpg`: matching cover stills.
- `videos/*.mp4`: original files kept so previously published URLs do not change. Not for new posts.
- Narrated promos (`reel-promo-30s.mp4`, `reel-promo-30s-framed.mp4`, `reel-hook-promo-4s.mp4`) are `excluded` until a narration-safe edit exists. Their mix was not replaced.

Theme A (SHA-256 `b1a8db25bd6ba3eb01ebe136221d72ea7ba1d8db985dc5c1da599bb8f5805570`) is the approved vocal file for these social clips, not in-game music. No share URL was supplied with the file.

Check the media with `python3 scripts/validate_social_assets.py`.

Game: https://zacharyryanschwartz-droid.github.io/petalspire/
