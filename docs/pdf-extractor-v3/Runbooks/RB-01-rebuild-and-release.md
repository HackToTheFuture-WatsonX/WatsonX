# RB-01 — Rebuild and Release a New Version

## When to run

Every time a shippable change lands on the release branch — hotfix, feature release, or dependency bump.

## Preconditions

- On the release branch (`main`) at the intended commit.
- Working tree is clean (`git status` is empty).
- Python 3.12 + Node.js 18 + Electron toolchain installed (see [Environment-Setup.md](../Environment-Setup.md)).
- The intended new version has been decided (SemVer — see [Versioning-Policy.md](../Versioning-Policy.md)).

## Steps

1. **Bump versions** in three files (same version everywhere):
   - `PDF Extractor V3\backend\main.py` → `APP_VERSION = "<new-version>"`.
   - `PDF Extractor V3\electron\package.json` → `"version": "<new-version>"`.
   - `PDF Extractor V3\frontend\package.json` → `"version": "<new-version>"`.

2. **Update the changelog**:
   - Add a new section to `docs/pdf-extractor-v3/Release-Notes.md` with the date, version, and bullet points describing what changed (user-visible language, not diff-quotes).

3. **Commit**:
   ```bat
   git add -A
   git commit -m "chore(release): <new-version>"
   ```

4. **Build**:
   ```bat
   cd "PDF Extractor V3"
   build_all.bat
   ```
   Wait for the three-step pipeline to complete. Total ~2–3 minutes.

5. **Verify build artefacts exist**:
   ```
   PDF Extractor V3\electron\dist\PDF-Extractor-V3-Setup-<new-version>.exe
   PDF Extractor V3\electron\dist\PDF-Extractor-V3-Portable-<new-version>.exe
   ```

6. **Smoke-test on a clean VM** — run the smoke-test checklist from [Deployment-Guide.md](../Deployment-Guide.md#smoke-test-checklist).

7. **Tag and push**:
   ```bat
   git tag -a v<new-version> -m "Release <new-version>"
   git push origin main
   git push origin v<new-version>
   ```

8. **Publish**:
   - Draft a GitHub release for tag `v<new-version>`.
   - Attach both `.exe` files.
   - Paste the [Release-Notes.md](../Release-Notes.md) section as the release description.
   - Publish.

9. **Distribute** to end-users via your team's normal channel (SharePoint / Teams / email).

## Verify

- Users report successful upgrade with no data loss.
- Backend log on the first user machine shows `Registered routes:` listing the same endpoints as previous release + any new ones.

## Rollback

If a regression is discovered post-release:

1. Immediately publish a `WARNING: bad release` message in your team's channel.
2. Delete the GitHub release artefacts (or mark as pre-release).
3. Users who already installed: guide them to install the previous version.
4. Do NOT tag `v<new-version>` again — bump to `v<new-version+1>` for the fix.
