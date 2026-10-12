# Security cleanup only Nick can do (from the 2026-10-07 QA)

Claude can't run these. They rewrite public history, change GitHub account settings or edit DNS. Do them in this order.

## 1. Purge the work email and the build cache from GitHub (P1)

The 2026-09-28 rewrite changed commit *authors* to the no-reply address, but not file *contents*. In 8 public commits, `CLAUDE.md`
still contains the old work email in a `git config user.email=` line (this public file deliberately doesn't repeat it). The pre-rewrite commits (8c16e85 … 1dc2afc) are also still
fetchable by SHA on GitHub, and 6 Actions runs show that email as the commit author. The same history carries a 149 MB
`DerivedData-xc27.0/` build cache (paths and a simulator id, nothing secret) and `data/wi/calibration.json` (aggregate rates measured
against Google 2021 data).

1. Install the tool: `brew install git-filter-repo`.
2. In `wi-eats/`, with everything committed, put the old work address in place of OLD_EMAIL (keep the quotes):

```bash
printf '%s==>329204362+nickstrom5@users.noreply.github.com\n' 'OLD_EMAIL' > /tmp/wi-email.txt
```

The first commits also carry the old contact address on wisconsineats.com, a domain a third party now owns (mail sent
there reaches them). Add it to the same file so the rewrite replaces it with the current contact:

```bash
printf 'hello@wisconsineats.com==>work-with-nick@gmail.com\n' >> /tmp/wi-email.txt
```

```bash
git filter-repo --force --replace-text /tmp/wi-email.txt --path DerivedData-xc27.0 --path data/wi/calibration.json --invert-paths
```

```bash
git remote add origin https://github.com/nickstrom5/wisconsin-eats.git
```

```bash
git grep -I -F 'OLD_EMAIL' $(git rev-list --all) | head
```

The last command must print nothing.

3. Force-push: `git push --force origin main`. This also publishes the site. Never push `backup-before-email-rewrite`; delete it
   locally once you're happy: `git branch -D backup-before-email-rewrite`.
4. Delete the old Actions runs (they show the old author):

```bash
gh run list -R nickstrom5/wisconsin-eats --limit 500 --json databaseId -q '.[].databaseId' | xargs -n1 gh run delete -R nickstrom5/wisconsin-eats
```

5. Ask GitHub to purge the dangling commits and cached views: https://support.github.com/request → "Remove sensitive data". List the
   repo and say the old commits contain a personal email. GitHub's guide: "Removing sensitive data from a repository".
6. Run the same check on the other public repos made from these prompts (chicago, the hub). `git log --all --format='%ae' | sort -u`
   should list only the no-reply address.

## 2. Verify eatsranked.com for GitHub Pages (P1)

Today `_github-pages-challenge-nickstrom5.eatsranked.com` doesn't exist, so if a state's repo is ever deleted, renamed, made private
or has Pages turned off, someone else could publish on that subdomain, including behind the app's privacy and terms links.

1. github.com/settings/pages_verified_domains → **Add a domain** → `eatsranked.com`.
2. GitHub shows a TXT record. Add it in Cloudflare DNS (name `_github-pages-challenge-nickstrom5`, the value GitHub shows) and keep
   it forever. Then click **Verify**. This covers every subdomain (wisconsin, chicago, and each new state).
3. When retiring a state site, delete its Cloudflare record **before** the repo or Pages.

## 3. Email spoofing record (P3)

Mail for eatsranked.com goes to Cloudflare Email Routing (MX route1–3), and there's no DMARC record. If nothing ever *sends* as
@eatsranked.com, add a Cloudflare TXT record `_dmarc` with `v=DMARC1; p=reject; adkim=s; aspf=s`. If something does send (a form
service, a newsletter), use `p=none` until it's set up with SPF/DKIM.

## 4. Optional: protect `main`

Pushing `main` publishes the site. After step 1, add a ruleset (repo Settings → Rules → Rulesets) that blocks force-pushes and
deletion on `main`. Lift it temporarily if history ever needs rewriting again.
