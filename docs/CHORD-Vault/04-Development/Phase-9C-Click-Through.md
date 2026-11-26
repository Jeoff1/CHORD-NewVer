# Phase 9C click-through test

A manual run through guided service planning ([[Design-Decisions]],
"Phase 9C") in a browser, after the automated checks pass. Each step says
what to do and what you should see. Tick a step when it behaves as
written; note anything else in the [[Development-Log]].

**Before you start**

- Run `.\scripts\check.ps1` on branch `phase-9c-guided-planning`; it must
  pass.
- Run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
  (it adds pypdf, which reads sermon PDFs).
- Run `.\.venv\Scripts\python.exe manage.py migrate` (it gives Pastoral
  Staff the permission to assign the team, and adds the sermon PDF to
  themes), then start the site
  (`manage.py runserver`) and the search worker (`manage.py run_worker`).
- Sign in as someone with the Pastoral Staff role. Have a second window
  signed in as a Team Member.

## 1. A new service guides the pastor

- [ ] **1.1** Worship › Add service; save it. The service page shows four
  steps: **Theme**, **Praise Team**, **Song Lineup**, **Confirm**, with
  Theme highlighted. Under it, a panel "Next: post the theme" with a
  **Post the theme** button.
- [ ] **1.2** Click **Post the theme**, fill it in and save. Back on the
  service page, Theme has a tick and the panel says "Next: assign the
  Praise Team", with **Assign the Praise Team** and **Skip for now**.
- [ ] **1.3** Click **Assign the Praise Team**. Assign one person to a
  part. The page stays open: "Praise Team so far" lists them. Assign a
  second person, then click **Done**.
- [ ] **1.4** The service page shows "2 assigned, 0 accepted" under Praise
  Team, and the panel says "Next: choose the songs".

## 2. Song Lineup on one page

- [ ] **2.1** Click **Choose the songs** (or the Song Lineup step). The
  page is titled "Song Lineup", its step is underlined, and it holds the
  suggestions: Find songs or Rank the song pool only.
- [ ] **2.2** Find songs. The progress shows on this page; when it ends,
  the ranked songs show here. Click **Save these songs as the lineup**.
- [ ] **2.3** The same page now shows the songs to review (move, lock,
  swap, keys), a **Spotify playlist** card saying how many songs will be
  saved and where (or that Spotify isn't set up), with Listen links, and
  the suggestions folded below. The one button is **Continue to confirm**.

## 3. Confirm with a rundown

- [ ] **3.1** Click **Continue to confirm**. The rundown shows the
  service's date, time and theme, the Praise Team with replies, the songs
  with slot, key and chord sheet, and "Before you confirm" warnings (for
  example songs without a chord sheet or key, people who haven't
  replied).
- [ ] **3.2** Click **Confirm lineup**. You're back on the service page:
  every step is ticked and the panel says "Lineup confirmed" with **Open
  the lineup**. If Spotify is connected, the lineup card shows the
  playlist; if saving failed, it shows **Save to Spotify**.

## 4. Other cases

- [ ] **4.1** On a new service, post the theme, then click **Skip for
  now**. You land on Song Lineup; back on the service page, after a
  search has run, the panel no longer asks for the team, and Praise Team
  still says "Nobody yet".
- [ ] **4.2** In the Team Member's window, open the same service. No
  steps, no panel, no suggestions; the lineup shows only once confirmed.
- [ ] **4.3** Settings › Labels: rename "Praise Team" to "Music Team".
  The step, the team card and the assign page use "Music Team".
- [ ] **4.4** Settings › Modules: switch Teams off. A service shows three
  steps (no team step). Switch Teams back on.

## 5. Sermon PDF

- [ ] **5.1** Edit a service's theme. Under the notes there is **Sermon
  PDF**. Attach a sermon saved as a PDF and save. A message says how many
  words were read; the theme card shows the file's name with "N words
  read for song suggestions".
- [ ] **5.2** Click the file's name: the PDF opens in a new tab.
- [ ] **5.3** In the Team Member's window, open the service: no PDF link.
- [ ] **5.4** On Song Lineup, find songs again. The suggestions and search
  phrases ("About this search") reflect the sermon's content, not only
  the title. Compare with a run before the PDF if you have one.
- [ ] **5.5** Attach a scanned PDF (a photo of a page): it is kept, with a
  message that no text could be read. Attach a file that isn't a PDF: it
  is refused.
- [ ] **5.6** Edit the theme, tick **Clear** under the PDF and save: the
  link is gone.

## 6. Main scripture from the Bible

- [ ] **6.1** Edit a theme. In **Main scripture** type `jn`: a list
  offers John (and books starting the same way). Type `jn 3:1`: verses of
  John 3 with their first words. Use the arrow keys and Enter, or click,
  to pick **John 3:16**. The verse's text shows under the field, marked
  World English Bible.
- [ ] **6.2** Type `ps 23` and pick **Psalm 23**: the whole psalm shows.
  Type `Various passages`: "Not found in the Bible", and the theme still
  saves.
- [ ] **6.3** Save with a real passage. The theme card has **Read** and
  the passage's reference; it opens the text. The Team Member sees it too.
- [ ] **6.4** Type `tob`: Tobit isn't offered. Settings › Worship ›
  Services › **Bible**: tick "Include the deuterocanonical books" and
  save. Now `tob` offers Tobit.
- [ ] **6.5** On Song Lineup, find songs again: the passage's words now
  count toward the match ("About this search" shows the phrases).
